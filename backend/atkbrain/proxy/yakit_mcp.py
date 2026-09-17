"""发现本机 Yak/Yakit MCP，并转发 tools/list 与 tools/call。

优先接已监听的 Streamable HTTP MCP（Cursor 的 user-yakit 同口）；
没有则拉起 `yak mcp --enable-all`。不 vendoring yakit 源码。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import settings

HIDDEN_TOOLS = frozenset({"mcp_auth"})
DEFAULT_MCP_PORT = 11432
_CLIENT_INFO = {"name": "atkbrain-flash", "version": "0.5.0"}
_PROTOCOL = "2025-03-26"


def _mcp_url(host: str, port: int, path: str = "/mcp") -> str:
    p = path if path.startswith("/") else f"/{path}"
    return f"http://{host}:{int(port)}{p}"


def settings_mcp_url() -> str:
    raw = (getattr(settings, "yakit_mcp_url", None) or "").strip()
    if raw:
        return raw.rstrip("/") if raw.endswith("/mcp") else (raw.rstrip("/") + "/mcp" if "/mcp" not in raw else raw)
    host = (getattr(settings, "yakit_mcp_host", None) or "127.0.0.1").strip() or "127.0.0.1"
    port = int(getattr(settings, "yakit_mcp_port", None) or DEFAULT_MCP_PORT)
    return _mcp_url(host, port)


OOB_HINTS = ("reverse", "dns", "dnslog", "oob", "facade", "icmp", "ldap")


def tools_have_oob(tools: list[dict[str, Any]]) -> bool:
    names = " ".join(str(t.get("name") or "").lower() for t in tools)
    return any(h in names for h in OOB_HINTS)


def full_mcp_url() -> str:
    host = (getattr(settings, "yakit_mcp_host", None) or "127.0.0.1").strip() or "127.0.0.1"
    port = int(getattr(settings, "yakit_mcp_full_port", None) or 11433)
    return _mcp_url(host, port)


def discover_mcp_urls() -> list[str]:
    """全能力口优先，再配置口 / Cursor 口 / 扫描 yak mcp 进程。去重保序。"""
    out: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        u = (url or "").strip().rstrip("/")
        if not u:
            return
        if not u.endswith("/mcp"):
            u = u + "/mcp"
        if u not in seen:
            seen.add(u)
            out.append(u)

    add(full_mcp_url())
    add(settings_mcp_url())
    add(_mcp_url("127.0.0.1", DEFAULT_MCP_PORT))
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                raw = open(f"/proc/{pid}/cmdline", "rb").read()
            except OSError:
                continue
            parts = [p.decode("utf-8", "replace") for p in raw.split(b"\0") if p]
            if not parts:
                continue
            blob = " ".join(parts).lower()
            if "yak" not in blob or "mcp" not in blob:
                continue
            host = "127.0.0.1"
            port = DEFAULT_MCP_PORT
            for i, tok in enumerate(parts):
                if tok in ("--host",) and i + 1 < len(parts):
                    host = parts[i + 1].strip() or host
                    if host in ("0.0.0.0", "::", "[::]"):
                        host = "127.0.0.1"
                if tok in ("--port",) and i + 1 < len(parts):
                    try:
                        port = int(parts[i + 1])
                    except (TypeError, ValueError):
                        pass
            add(_mcp_url(host, port))
    except Exception:
        pass
    return out


def parse_rpc_body(resp: httpx.Response) -> dict[str, Any]:
    text = resp.text or ""
    ctype = (resp.headers.get("content-type") or "").lower()
    if "text/event-stream" in ctype or text.startswith("event:") or "\ndata:" in text[:200]:
        data_line = ""
        for line in text.splitlines():
            if line.startswith("data:"):
                data_line = line[5:].strip()
        if data_line:
            obj = json.loads(data_line)
            return obj if isinstance(obj, dict) else {}
    if not text.strip():
        return {}
    obj = json.loads(text)
    return obj if isinstance(obj, dict) else {}


class YakMcpClient:
    """一个 Streamable HTTP MCP 会话。失败时换 URL 并可选拉起 yak mcp。"""

    def __init__(self) -> None:
        self.url: str = settings_mcp_url()
        self.session_id: str | None = None
        self.tools: list[dict[str, Any]] = []
        self.tools_at: float = 0.0
        self.last_error: str | None = None
        self.server_name: str = ""
        self._cli: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._spawned: asyncio.subprocess.Process | None = None
        self._spawned_url: str | None = None
        self.has_oob: bool = False
        self._full_attempted: bool = False
        self._ensured_at: float = 0.0
        self.epoch: int = 0

    def _client(self) -> httpx.AsyncClient:
        if self._cli is None or self._cli.is_closed:
            self._cli = httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=1.8), trust_env=False)
        return self._cli

    def _headers(self, *, with_session: bool = True) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": _PROTOCOL,
        }
        if with_session and self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    async def close(self) -> None:
        if self._cli is not None:
            try:
                await self._cli.aclose()
            except Exception:
                pass
            self._cli = None
        proc = self._spawned
        self._spawned = None
        if proc and proc.returncode is None:
            try:
                proc.terminate()
            except Exception:
                pass

    async def _post(self, payload: dict[str, Any], *, with_session: bool = True) -> tuple[httpx.Response, dict[str, Any]]:
        r = await self._client().post(self.url, json=payload, headers=self._headers(with_session=with_session))
        body = parse_rpc_body(r)
        return r, body

    async def _initialize(self, url: str) -> bool:
        prev = self.url
        self.url = url
        self.session_id = None
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": _PROTOCOL,
                "capabilities": {},
                "clientInfo": _CLIENT_INFO,
            },
        }
        try:
            r, body = await self._post(payload, with_session=False)
        except Exception as e:
            self.last_error = f"MCP 连接失败：{e}"[:200]
            return False
        if r.status_code >= 400 or "error" in body:
            err = body.get("error") if isinstance(body.get("error"), dict) else {}
            self.last_error = str(err.get("message") or r.text or r.status_code)[:200]
            return False
        sid = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
        result = body.get("result") if isinstance(body.get("result"), dict) else {}
        if not sid:
            sid = str(result.get("sessionId") or "") or None
        self.session_id = sid
        info = result.get("serverInfo") if isinstance(result.get("serverInfo"), dict) else {}
        self.server_name = str(info.get("name") or "Yaklang MCP")
        try:
            await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, with_session=True)
        except Exception:
            pass
        if (url or "") != (prev or ""):
            self.epoch += 1
        self.last_error = None
        return True

    async def _fetch_tools(self) -> list[dict[str, Any]]:
        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        try:
            r, body = await self._post(payload)
        except Exception as e:
            self.last_error = str(e)[:200]
            return []
        if r.status_code in (400, 404) or "error" in body:
            return []
        result = body.get("result") if isinstance(body.get("result"), dict) else {}
        tools = result.get("tools") if isinstance(result.get("tools"), list) else []
        self.tools = [t for t in tools if isinstance(t, dict) and t.get("name")]
        self.tools_at = time.monotonic()
        self.has_oob = tools_have_oob(self.tools)
        self.last_error = None
        return self.tools

    async def _spawn_mcp(self, *, port: int, enable_all: bool = True) -> str | None:
        yak = shutil.which("yak") or "/usr/local/bin/yak"
        if not os.path.isfile(yak):
            self.last_error = "未找到 yak 可执行文件"
            return None
        host = (getattr(settings, "yakit_mcp_host", None) or "127.0.0.1").strip() or "127.0.0.1"
        url = _mcp_url(host, int(port))
        if await self._initialize(url):
            await self._fetch_tools()
            return url
        log_path = str(settings.data_dir / "yakit-mcp.log")
        try:
            logf = open(log_path, "ab")
        except Exception:
            logf = asyncio.subprocess.DEVNULL
        cmd = [
            yak, "mcp",
            "--transport", "streamable_http",
            "--host", host,
            "--port", str(int(port)),
        ]
        if enable_all:
            cmd.append("--enable-all")
        try:
            self._spawned = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=logf,
                stderr=logf,
                start_new_session=True,
            )
        except Exception as e:
            self.last_error = f"拉起 yak mcp 失败：{e}"[:200]
            return None
        self._spawned_url = url
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            await asyncio.sleep(0.35)
            if await self._initialize(url):
                await self._fetch_tools()
                return url
        self.last_error = self.last_error or "yak mcp 已启动但尚未就绪"
        return None

    async def ensure(self, *, spawn: bool = True) -> bool:
        async with self._lock:
            now = time.monotonic()
            if self.session_id and self.has_oob:
                return True
            if self.session_id and (now - self._ensured_at) < 20.0 and (self._full_attempted or not spawn):
                return True
            ranked: list[tuple[int, bool, str]] = []
            for url in discover_mcp_urls():
                if not await self._initialize(url):
                    continue
                tools = await self._fetch_tools()
                ranked.append((len(tools), tools_have_oob(tools), url))
            ranked.sort(key=lambda x: (x[1], x[0]), reverse=True)
            best = ranked[0] if ranked else None
            need_full = spawn and (not best or not best[1])
            if need_full:
                self._full_attempted = True
                full_port = int(getattr(settings, "yakit_mcp_full_port", None) or 11433)
                spawned = await self._spawn_mcp(port=full_port, enable_all=True)
                if spawned and self.session_id:
                    self._ensured_at = time.monotonic()
                    return True
            if best:
                if self.url != best[2] or not self.session_id:
                    if await self._initialize(best[2]):
                        await self._fetch_tools()
                self._ensured_at = time.monotonic()
                return bool(self.session_id)
            if not spawn:
                return False
            fallback = int(getattr(settings, "yakit_mcp_port", None) or DEFAULT_MCP_PORT)
            spawned = await self._spawn_mcp(port=fallback, enable_all=True)
            self._full_attempted = True
            self._ensured_at = time.monotonic()
            return bool(spawned and self.session_id)

    def invalidate(self) -> None:
        self.session_id = None
        self.tools = []
        self.tools_at = 0.0
        self.has_oob = False

    async def list_tools(self, *, ttl: float = 8.0, spawn: bool = False) -> list[dict[str, Any]]:
        now = time.monotonic()
        if self.tools and (now - self.tools_at) < ttl:
            return self.tools
        if not await self.ensure(spawn=spawn):
            return []
        if self.tools and (time.monotonic() - self.tools_at) < ttl:
            return self.tools
        tools = await self._fetch_tools()
        if tools:
            return tools
        self.invalidate()
        if await self.ensure(spawn=spawn):
            return await self._fetch_tools()
        return []

    async def ping(self) -> bool:
        tools = await self.list_tools(ttl=2.0)
        return bool(self.session_id) and self.last_error is None and isinstance(tools, list)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if not await self.ensure(spawn=True):
            return {
                "isError": True,
                "content": [{"type": "text", "text": self.last_error or "Yakit MCP 未就绪"}],
            }
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        try:
            r, body = await self._post(payload)
        except Exception as e:
            return {"isError": True, "content": [{"type": "text", "text": str(e)[:400]}]}
        if "error" in body:
            err = body.get("error") if isinstance(body.get("error"), dict) else {}
            msg = str(err.get("message") or body)[:800]
            if r.status_code in (400, 404) or "session" in msg.lower():
                self.invalidate()
            return {"isError": True, "content": [{"type": "text", "text": msg}]}
        result = body.get("result")
        if isinstance(result, dict):
            return result
        return {"content": [{"type": "text", "text": str(result)}], "isError": False}


mcp_client = YakMcpClient()


def mcp_host_port(url: str | None = None) -> tuple[str, int]:
    u = urlparse(url or mcp_client.url or settings_mcp_url())
    host = u.hostname or "127.0.0.1"
    port = int(u.port or DEFAULT_MCP_PORT)
    return host, port
