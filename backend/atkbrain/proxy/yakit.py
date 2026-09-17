"""Yakit MITM + MCP 桥：开关、证书、下游池、从者工具注入。"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import settings
from ..objective import objective_allows_flag
from .pool import pool
from .yakit_mcp import HIDDEN_TOOLS, mcp_client, mcp_host_port, settings_mcp_url

NO_DIRECT_MSG = "红队/SRC 出口代理池暂无存活节点，拒绝直连以免暴露真实 IP"
MITM_FAIL_MSG = "Yakit MITM 未监听，拒绝出网以免流量既不进 History 又可能暴露真实 IP"

_SEND_TOOLS = frozenset({
    "http_fuzzer", "web_crawler", "start_mitm_v2",
    "create_web_fuzzer_tab", "create_web_fuzzer_tabs", "update_web_fuzzer_tab",
})
_PROXY_KEYS = frozenset({"proxy", "downstreamproxy", "downstream_proxy"})
_HOST_HDR = re.compile(r"(?im)^Host:\s*([^\r\n]+)")
_STATUS_TTL = 1.6
_DECRYPT_TTL = 20.0
_DECRYPT_FAIL_TTL = 2.0
_SCOPE_HOST_TTL = 8.0
_ECHO_IP_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def parse_echo_ip(status_code: int | None, body: str | None) -> str | None:
    """icanhazip 只接受 200 + 首行纯 IPv4。Yakit 错误页里的 IP 不算出口。"""
    try:
        code = int(status_code or 0)
    except (TypeError, ValueError):
        return None
    if code != 200:
        return None
    text = (body or "").strip()
    if not text:
        return None
    low = text.lower()
    if "<html" in low or "<!doctype" in low or "yakit" in low or "proxyerror" in low:
        return None
    first = text.splitlines()[0].strip()
    return first if _ECHO_IP_RE.fullmatch(first) else None


def engine_cert_stale(
    *,
    bound_url: str | None,
    bound_fp: str | None,
    live_url: str | None,
    live_fp: str | None = None,
) -> bool:
    """磁盘 CA 必须绑在当前 MCP 上；换引擎或指纹对不上就视为过期。"""
    bu = (bound_url or "").strip().rstrip("/")
    lu = (live_url or "").strip().rstrip("/")
    bf = (bound_fp or "").strip().upper()
    lf = (live_fp or "").strip().upper()
    if not bu or not bf:
        return True
    if lu and bu != lu:
        return True
    if lf and bf != lf:
        return True
    return False


def cert_path() -> Path:
    return Path(settings.data_dir) / "yakit-mitm-ca.pem"


def _settings_file() -> Path:
    return Path(settings.data_dir) / "proxy-settings.json"


def _read_settings() -> dict[str, Any]:
    p = _settings_file()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_settings(updates: dict[str, Any]) -> None:
    p = _settings_file()
    data = _read_settings()
    data.update(updates)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def _project_cfg(project: dict | None) -> dict[str, Any]:
    if not isinstance(project, dict):
        return {}
    cfg = project.get("config")
    if isinstance(cfg, dict):
        return cfg
    return {}


def should_use_yakit(objective: str | None = None, project: dict | None = None) -> bool:
    """顶栏开关开，且非 CTF（除非项目/全局 opt-in）。"""
    if not yakit.enabled:
        return False
    if not objective_allows_flag(objective):
        return True
    cfg = _project_cfg(project)
    if bool(cfg.get("yakit_mitm")):
        return True
    return bool(getattr(settings, "yakit_mitm_ctf", False))


def mitm_listen() -> tuple[str, int]:
    host = (getattr(settings, "yakit_mitm_host", None) or "127.0.0.1").strip() or "127.0.0.1"
    port = int(getattr(settings, "yakit_mitm_port", None) or 8084)
    try:
        inst = int(getattr(yakit, "listen_port", 0) or 0)
        if inst:
            port = inst
    except Exception:
        pass
    return host, port


def mitm_proxy_url() -> str:
    host, port = mitm_listen()
    return f"http://{host}:{port}"


def port_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.4):
            return True
    except Exception:
        if host == "127.0.0.1":
            try:
                with socket.create_connection(("0.0.0.0", int(port)), timeout=0.2):
                    return True
            except Exception:
                pass
        return False


def _openssl_cert_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "readable": False,
        "expired": True,
        "fingerprint": "",
        "expires_at": "",
        "error": None,
    }
    if not path.is_file():
        info["error"] = "未下载 MITM 证书"
        return info
    try:
        path.read_text(encoding="utf-8")
        info["readable"] = True
    except Exception as e:
        info["error"] = f"证书不可读：{e}"[:160]
        return info
    try:
        import subprocess
        end = subprocess.check_output(
            ["openssl", "x509", "-enddate", "-noout", "-in", str(path)],
            timeout=4, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        fp = subprocess.check_output(
            ["openssl", "x509", "-fingerprint", "-sha256", "-noout", "-in", str(path)],
            timeout=4, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception as e:
        info["error"] = f"解析证书失败：{e}"[:160]
        return info
    raw = end.split("=", 1)[-1].strip()
    info["expires_at"] = raw
    try:
        dt = datetime.strptime(raw.replace("  ", " "), "%b %d %H:%M:%S %Y GMT").replace(tzinfo=timezone.utc)
        info["expired"] = dt <= datetime.now(timezone.utc)
    except Exception:
        info["expired"] = False
    if "=" in fp:
        info["fingerprint"] = fp.split("=", 1)[-1].strip()
    else:
        info["fingerprint"] = fp
    if info["expired"]:
        info["error"] = "证书已过期"
    return info


def _extract_pem(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if "BEGIN CERTIFICATE" in raw:
        start = raw.find("-----BEGIN CERTIFICATE-----")
        end = raw.find("-----END CERTIFICATE-----")
        if start >= 0 and end > start:
            return raw[start:end + len("-----END CERTIFICATE-----")] + "\n"
    try:
        obj = json.loads(raw)
    except Exception:
        obj = None
    if isinstance(obj, dict):
        b64 = obj.get("CaCerts") or obj.get("caCerts") or obj.get("ca_certs")
        if isinstance(b64, str) and b64.strip():
            try:
                pem = base64.b64decode(b64).decode("utf-8", "replace")
            except Exception:
                pem = ""
            if "BEGIN CERTIFICATE" in pem:
                return _extract_pem(pem)
        local = obj.get("LocalFile") or obj.get("localFile")
        if isinstance(local, str) and os.path.isfile(local):
            try:
                return _extract_pem(Path(local).read_text(encoding="utf-8"))
            except Exception:
                pass
    return None


def _content_text(result: dict[str, Any]) -> str:
    parts: list[str] = []
    content = result.get("content") if isinstance(result, dict) else None
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("text"):
                parts.append(str(c.get("text")))
    if not parts and isinstance(result, dict) and result.get("text"):
        parts.append(str(result.get("text")))
    return "\n".join(parts)


def _hosts_from_text(s: str) -> list[str]:
    hosts: list[str] = []
    blob = (s or "").strip()
    if not blob:
        return hosts
    if "://" in blob.split()[0] if blob.split() else "":
        try:
            h = urlparse(blob.split()[0]).hostname
            if h:
                hosts.append(h.lower())
        except Exception:
            pass
    m = _HOST_HDR.search(blob)
    if m:
        hosts.append(m.group(1).split(":")[0].strip().lower())
    if re.match(r"^[A-Za-z0-9._-]+(?::\d+)?$", blob) and "://" not in blob and "\n" not in blob:
        hosts.append(blob.split(":")[0].lower())
    for m in re.finditer(r"https?://([^/\s:\"']+)", blob, re.I):
        hosts.append(m.group(1).lower())
    return [h for h in hosts if h and h not in (".", "localhost")]


def _walk_hosts(obj: Any, acc: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in {
                "url", "target", "host", "hostname", "actualaddr", "sni",
                "request", "requestraw", "packet", "searchurl",
            } and isinstance(v, str):
                acc.extend(_hosts_from_text(v))
            elif lk == "batchtarget" and isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        acc.extend(_hosts_from_text(item))
            else:
                _walk_hosts(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _walk_hosts(item, acc)
    elif isinstance(obj, str) and ("://" in obj or obj.lower().startswith("host:")):
        acc.extend(_hosts_from_text(obj))


def _force_proxy_fields(obj: Any, proxy_url: str, *, mitm: bool) -> None:
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            lk = str(k).lower()
            if lk in _PROXY_KEYS:
                obj[k] = proxy_url
            elif lk in ("disablesystemproxy", "nosystemproxy"):
                obj[k] = True
            else:
                _force_proxy_fields(obj[k], proxy_url, mitm=mitm)
        if mitm:
            host, port = mitm_listen()
            if "host" in obj or "port" in obj:
                obj["host"] = host
                obj["port"] = port
            obj["disableSystemProxy"] = True
            obj["downstreamProxy"] = proxy_url
    elif isinstance(obj, list):
        for item in obj:
            _force_proxy_fields(item, proxy_url, mitm=False)


def _schema_has_proxy(schema: dict | None) -> bool:
    props = (schema or {}).get("properties") if isinstance(schema, dict) else None
    if not isinstance(props, dict):
        return False
    return any(str(k).lower() in _PROXY_KEYS for k in props)


def _is_send_tool(name: str, args: dict, schema: dict | None) -> bool:
    if name in _SEND_TOOLS:
        return True
    if name in {
        "query_http_flow", "delete_http_flow", "get_mitm_filter", "set_mitm_filter",
        "download_mitm_cert", "get_current_rules", "set_current_rules",
        "query_mitm_replacer_rules", "set_tag_for_http_flow",
        "query_web_fuzzer_tabs", "delete_web_fuzzer_tabs", "manage_web_fuzzer_tab_group",
    }:
        return False
    if any(str(k).lower() in _PROXY_KEYS for k in (args or {})):
        return True
    return _schema_has_proxy(schema)


@dataclass
class Egress:
    mode: str  # mitm | pool | direct
    proxy: str | None = None
    extra_env: dict[str, str] | None = None
    refuse: bool = False
    reason: str = ""


def resolve_egress(objective: str | None = None, project: dict | None = None) -> Egress:
    """命令/HTTP 出网第一跳。MITM 与 proxychains 互斥。"""
    must = False
    try:
        must = pool.must_proxy(objective)
    except Exception:
        must = False
    if should_use_yakit(objective, project):
        if must and not yakit.verified_exit_ip:
            return Egress(mode="mitm", refuse=True, reason=NO_DIRECT_MSG)
        if not yakit.our_mitm_listening():
            return Egress(mode="mitm", refuse=True, reason=MITM_FAIL_MSG)
        return Egress(mode="mitm", proxy=mitm_proxy_url(), extra_env=yakit.http_env())
    if must:
        px = pool.pick(prefer_http=True)
        if not px:
            return Egress(mode="pool", refuse=True, reason=NO_DIRECT_MSG)
        return Egress(mode="pool", proxy=px, extra_env=pool.proxy_env(px))
    return Egress(mode="direct")


async def prepare_egress(objective: str | None = None, project: dict | None = None) -> Egress:
    """等池子 + 验收 MITM 下游后再给出网第一跳。已验收则不再每条请求 wait_pick/ensure。"""
    if should_use_yakit(objective, project):
        must = False
        try:
            must = pool.must_proxy(objective)
        except Exception:
            must = False
        if must and yakit.verified_exit_ip and yakit.our_mitm_listening():
            return resolve_egress(objective, project)
        try:
            if must:
                await pool.wait_pick(8.0, prefer_http=True)
        except Exception:
            pass
        try:
            await yakit.ensure_mitm()
        except Exception:
            pass
    return resolve_egress(objective, project)


class YakitBridge:
    enabled: bool = False

    def __init__(self) -> None:
        self.enabled = False
        self.downstream: str = ""
        self.listen_port = int(getattr(settings, "yakit_mitm_port", None) or 8084)
        self.listen_owned = False
        self.applied_downstream: str | None = None
        self.verified_exit_ip: str | None = None
        self.backup_text: str = ""
        self.last_good_proxy: str = ""
        self.last_error: str | None = None
        self._status_cache: dict[str, Any] | None = None
        self._status_at: float = 0.0
        self._decrypt_ok: bool | None = None
        self._decrypt_at: float = 0.0
        self._decrypt_port: int | None = None
        self._cert_mcp_url: str | None = None
        self._cert_fp: str = ""
        self._engine_url: str | None = None
        self._mcp_epoch: int = -1
        self._direct_ip: str | None = None
        self._direct_at: float = 0.0
        self._leak_at: float = 0.0
        self._down_fail: dict[str, float] = {}
        self._ensure_lock = asyncio.Lock()
        self._sync_lock = asyncio.Lock()
        self._sync_task: asyncio.Task | None = None
        self._bg: asyncio.Task | None = None
        self._scope_ok: dict[str, float] = {}

    def load(self) -> None:
        data = _read_settings()
        self.enabled = bool(data.get("yakit_enabled"))
        self.backup_text = str(data.get("yakit_backup_text") or "")
        self.last_good_proxy = str(data.get("yakit_last_good_proxy") or "")
        self._cert_mcp_url = str(data.get("yakit_cert_mcp_url") or "") or None
        self._cert_fp = str(data.get("yakit_cert_fp") or "")

    def save(self) -> None:
        _write_settings({
            "yakit_enabled": bool(self.enabled),
            "yakit_backup_text": self.backup_text,
            "yakit_last_good_proxy": self.last_good_proxy,
            "yakit_cert_mcp_url": self._cert_mcp_url or "",
            "yakit_cert_fp": self._cert_fp or "",
        })

    def http_env(self) -> dict[str, str]:
        url = mitm_proxy_url()
        env = {
            "http_proxy": url, "https_proxy": url,
            "HTTP_PROXY": url, "HTTPS_PROXY": url,
            "ALL_PROXY": url, "all_proxy": url,
            "no_proxy": "127.0.0.1,localhost,::1",
            "NO_PROXY": "127.0.0.1,localhost,::1",
            "ATKBRAIN_YAKIT_MITM": "1",
        }
        ca = cert_path()
        if ca.is_file():
            p = str(ca)
            env.update({
                "SSL_CERT_FILE": p,
                "REQUESTS_CA_BUNDLE": p,
                "CURL_CA_BUNDLE": p,
                "GIT_SSL_CAINFO": p,
            "NODE_EXTRA_CA_CERTS": p,
                })
        return env

    def our_mitm_listening(self) -> bool:
        """只认本桥 start_mitm 拉起的口，不把别人占用的 8084 当成自己的 MITM。"""
        if not self.listen_owned:
            return False
        host, port = mitm_listen()
        return port_listening(host, port)

    def note_pool_changed(self) -> None:
        if not self.enabled:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._sync_task and not self._sync_task.done():
            return
        self._sync_task = loop.create_task(self._debounced_sync())

    async def _debounced_sync(self) -> None:
        await asyncio.sleep(0.45)
        try:
            await self.sync_downstream()
        except Exception:
            pass

    async def startup(self) -> None:
        self.load()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._bg is None or self._bg.done():
            self._bg = loop.create_task(self._watch())
        if self.enabled:
            loop.create_task(self.ensure_ready())

    async def _watch(self) -> None:
        while True:
            try:
                if self.enabled:
                    await self.ensure_ready()
                    await self.sync_downstream()
                    await self._reverify_exit()
                await self.status(force=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(4.0)

    async def set_enabled(self, on: bool) -> dict[str, Any]:
        self.enabled = bool(on)
        self.save()
        self._status_cache = None
        if self.enabled:
            await self.ensure_ready()
            await self.sync_downstream()
        return await self.status(force=True)

    async def ensure_ready(self) -> None:
        async with self._ensure_lock:
            ok = await mcp_client.ensure(spawn=True)
            if not ok:
                self.last_error = mcp_client.last_error
                return
            live_url = mcp_client.url or ""
            live_epoch = int(getattr(mcp_client, "epoch", 0) or 0)
            switched = live_epoch != self._mcp_epoch or (live_url and live_url != (self._engine_url or ""))
            if switched:
                self._detach_foreign_engine()
                self._mcp_epoch = live_epoch
                self._engine_url = live_url
            try:
                await self.ensure_cert(force=switched)
            except Exception as e:
                self.last_error = f"证书：{e}"[:200]
            try:
                await self.ensure_mitm()
            except Exception as e:
                self.last_error = f"MITM：{e}"[:200]

    def _detach_foreign_engine(self) -> None:
        """换 MCP 引擎后旧口/旧 CA 一律作废，禁止拿 11432 的 8084 去验 11433 的证。"""
        self.listen_owned = False
        self.verified_exit_ip = None
        self.applied_downstream = None
        self.downstream = ""
        self._decrypt_ok = None
        self._decrypt_port = None
        self._status_cache = None

    async def ensure_cert(self, *, force: bool = False) -> Path:
        path = cert_path()
        url = mcp_client.url or ""
        info = _openssl_cert_info(path)
        stale = engine_cert_stale(
            bound_url=self._cert_mcp_url,
            bound_fp=self._cert_fp or info.get("fingerprint"),
            live_url=url,
        )
        if not force and not stale and info.get("readable") and not info.get("expired"):
            return path
        result = await mcp_client.call_tool("download_mitm_cert", {})
        if result.get("isError"):
            raise RuntimeError(_content_text(result) or "download_mitm_cert 失败")
        pem = _extract_pem(_content_text(result))
        if not pem:
            raise RuntimeError("MCP 未返回可用的 MITM CA PEM")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pem, encoding="utf-8")
        os.chmod(path, 0o644)
        info = _openssl_cert_info(path)
        self._cert_mcp_url = url
        self._cert_fp = str(info.get("fingerprint") or "")
        self._decrypt_ok = None
        self._status_cache = None
        self.save()
        return path

    async def _bind_live_cert(self) -> bool:
        """本桥 MITM 起来后必须能用当前 CA 校验叶子证，否则立即重拉 CA。"""
        self._decrypt_ok = None
        if await self._https_decrypt_ok():
            return True
        try:
            await self.ensure_cert(force=True)
        except Exception:
            return False
        self._decrypt_ok = None
        return await self._https_decrypt_ok()

    def _exclude_filter(self) -> dict[str, Any]:
        api_port = int(getattr(settings, "port", 2333) or 2333)
        fe_port = int(getattr(settings, "frontend_port", 2334) or 2334)
        return {
            "filterData": {
                "excludeHostnames": [
                    {
                        "matcherType": "regexp",
                        "ruleName": "atkbrain-console",
                        "group": [
                            r"127\.0\.0\.1:2333", r"localhost:2333",
                            r"127\.0\.0\.1:2334", r"localhost:2334",
                            rf"127\.0\.0\.1:{api_port}", rf"localhost:{api_port}",
                            rf"127\.0\.0\.1:{fe_port}", rf"localhost:{fe_port}",
                            r"api\.deepseek\.com", r".*\.deepseek\.com",
                        ],
                    },
                    {
                        "matcherType": "word",
                        "ruleName": "deepseek",
                        "group": ["api.deepseek.com", "deepseek.com"],
                    },
                ],
                "excludeUri": [
                    {
                        "matcherType": "regexp",
                        "ruleName": "flash-ports",
                        "group": [rf":{api_port}(/|$)", rf":{fe_port}(/|$)"],
                    },
                ],
            }
        }

    def _backup_urls(self) -> list[str]:
        from .pool import parse_proxy_line
        out: list[str] = []
        seen: set[str] = set()
        for line in (self.backup_text or "").splitlines():
            u = parse_proxy_line(line)
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def _downstream_candidates(self, exclude: set[str] | None = None) -> list[str]:
        skip = set(exclude or ())
        now = time.monotonic()
        for url, until in list(self._down_fail.items()):
            if until > now:
                skip.add(url)
            else:
                self._down_fail.pop(url, None)
        out: list[str] = []
        seen: set[str] = set()

        def add(url: str | None) -> None:
            u = (url or "").strip()
            if not u or u in seen or u in skip:
                return
            seen.add(u)
            out.append(u)

        try:
            add(pool.current_url())
        except Exception:
            pass
        try:
            for u in pool.mitm_candidates(16, exclude=skip):
                add(u)
        except Exception:
            pass
        for u in self._backup_urls():
            add(u)
        add(self.last_good_proxy)
        return out

    def _choose_listen_port(self, host: str) -> int:
        """start_mitm_v2 不会改已经在听的口的下游。只用空闲端口。"""
        base = int(getattr(settings, "yakit_mitm_port", None) or 8084)
        for i in range(0, 24):
            p = base + i
            if not port_listening(host, p):
                return p
        raise RuntimeError("无空闲 MITM 端口（8084–8107 都被占用）")

    async def _cached_direct_ip(self) -> str | None:
        now = time.monotonic()
        if self._direct_ip and (now - self._direct_at) < 45.0:
            return self._direct_ip
        try:
            from .pool import _probe_exit
            ip = await _probe_exit(None)
        except Exception:
            ip = None
        if not ip:
            try:
                async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, trust_env=False) as cli:
                    r = await cli.get("https://ipv4.icanhazip.com")
                    ip = parse_echo_ip(r.status_code, r.text)
            except Exception:
                ip = None
        self._direct_ip = ip
        self._direct_at = now
        return ip

    async def _echo_via_mitm(self, host: str | None = None, port: int | None = None) -> str | None:
        h, p = mitm_listen()
        host = host or h
        port = int(port or p)
        proxy = f"http://{host}:{port}"
        try:
            async with httpx.AsyncClient(
                timeout=8.0, follow_redirects=True, verify=False, trust_env=False, proxy=proxy,
            ) as cli:
                r = await cli.get("https://ipv4.icanhazip.com")
            return parse_echo_ip(r.status_code, r.text)
        except Exception:
            return None

    async def _reverify_exit(self) -> None:
        if not self.enabled or not pool.enabled:
            return
        now = time.monotonic()
        if self._leak_at and (now - self._leak_at) < 20.0:
            return
        self._leak_at = now
        if not self.verified_exit_ip:
            return
        via = await self._echo_via_mitm()
        direct = await self._cached_direct_ip()
        if via and direct and via == direct:
            self.verified_exit_ip = None
            self.applied_downstream = None
            self.last_error = "MITM 下游失效，出口变回本机 IP，正在换节点"
            await self.ensure_mitm()
            return
        if via:
            # 顶栏必须跟当前 MITM 的 icanhazip，不能一直显示启动时缓存的旧 IP。
            self.verified_exit_ip = via
            self.last_error = None
            try:
                pool.exit_ip = via
                if self.applied_downstream:
                    for item in pool.live:
                        if item.url == self.applied_downstream:
                            item.exit_ip = via
                            break
            except Exception:
                pass

    async def set_backup_text(self, text: str) -> dict[str, Any]:
        self.backup_text = str(text or "")
        self.save()
        if self.enabled:
            self.applied_downstream = None
            self.verified_exit_ip = None
            await self.ensure_mitm()
        return await self.status(force=True)

    def _pool_downstream(self) -> str:
        if self.applied_downstream:
            return self.applied_downstream
        cand = self._downstream_candidates()
        return cand[0] if cand else ""

    async def ensure_mitm(self) -> None:
        async with self._sync_lock:
            await self._ensure_mitm_locked()

    async def _ensure_mitm_locked(self) -> None:
        if not pool.enabled:
            if not port_listening(*mitm_listen()):
                await self._start_fresh_mitm("")
            return
        downs = self._downstream_candidates()
        if not downs:
            try:
                await pool.wait_pick(8.0, prefer_http=True)
            except Exception:
                pass
            downs = self._downstream_candidates()
        if not downs:
            self.last_error = NO_DIRECT_MSG
            self.verified_exit_ip = None
            return
        want = ""
        try:
            want = (pool.current_url() or "").strip()
        except Exception:
            want = ""
        if (
            self.verified_exit_ip
            and self.applied_downstream
            and port_listening(*mitm_listen())
            and (not want or self.applied_downstream == want)
        ):
            self.downstream = self.applied_downstream or ""
            self.last_error = None
            return
        await self._apply_mitm_candidates(downs)

    async def _apply_mitm_candidates(self, downs: list[str]) -> None:
        host = (getattr(settings, "yakit_mitm_host", None) or "127.0.0.1").strip() or "127.0.0.1"
        direct = await self._cached_direct_ip()
        last_err: Exception | None = None
        tried: set[str] = set()
        for url in downs[:8]:
            if url in tried:
                continue
            tried.add(url)
            try:
                port = self._choose_listen_port(host)
                await self._start_mitm(host, port, url)
                via = await self._echo_via_mitm(host, port)
                if not via:
                    raise RuntimeError("经 MITM 打 icanhazip 失败")
                if direct and via == direct:
                    try:
                        pool.drop(url)
                    except Exception:
                        pass
                    raise RuntimeError(f"下游 {url} 未改出口（仍是本机 {via}）")
                self.listen_port = int(port)
                self.listen_owned = True
                self.applied_downstream = url
                self.downstream = url
                self.verified_exit_ip = via
                self.last_good_proxy = url
                self.last_error = None
                try:
                    pool.exit_ip = via
                    pool._current_url = url
                    for item in pool.live:
                        if item.url == url:
                            item.exit_ip = via
                            break
                except Exception:
                    pass
                self.save()
                try:
                    await self._bind_live_cert()
                except Exception:
                    pass
                try:
                    await mcp_client.call_tool("set_mitm_filter", self._exclude_filter())
                except Exception:
                    pass
                return
            except Exception as e:
                last_err = e
                self._down_fail[url] = time.monotonic() + 90.0
                try:
                    pool.drop(url)
                except Exception:
                    pass
                continue
        self.verified_exit_ip = None
        self.applied_downstream = None
        self.last_error = str(last_err) if last_err else NO_DIRECT_MSG

    async def _start_fresh_mitm(self, down: str) -> None:
        host = (getattr(settings, "yakit_mitm_host", None) or "127.0.0.1").strip() or "127.0.0.1"
        port = self._choose_listen_port(host)
        await self._start_mitm(host, port, down)
        self.listen_port = int(port)
        self.listen_owned = True
        self.applied_downstream = down
        self.downstream = down
        self.verified_exit_ip = None
        self.last_error = None
        try:
            await self._bind_live_cert()
        except Exception:
            pass
        try:
            await mcp_client.call_tool("set_mitm_filter", self._exclude_filter())
        except Exception:
            pass

    async def _wait_listen(self, host: str, port: int, timeout: float = 8.0) -> bool:
        deadline = time.monotonic() + max(0.5, float(timeout))
        while time.monotonic() < deadline:
            if port_listening(host, port):
                return True
            await asyncio.sleep(0.2)
        return port_listening(host, port)

    async def _start_mitm(self, host: str, port: int, down: str) -> dict[str, Any]:
        args = {
            "host": host,
            "port": int(port),
            "disableSystemProxy": True,
            "downstreamProxy": down or "",
        }
        result = await mcp_client.call_tool("start_mitm_v2", args)
        ok = await self._wait_listen(host, port, 8.0)
        if result.get("isError") and not ok:
            raise RuntimeError(_content_text(result) or "start_mitm_v2 失败")
        if not ok:
            raise RuntimeError(f"MITM 未在 {host}:{port} 监听")
        self.listen_port = int(port)
        self.listen_owned = True
        self._decrypt_ok = None
        self._decrypt_port = None
        return result

    async def sync_downstream(self) -> None:
        if not self.enabled:
            return
        await self.ensure_mitm()

    async def _https_decrypt_ok(self) -> bool:
        now = time.monotonic()
        host, port = mitm_listen()
        if not self.listen_owned:
            self._decrypt_ok = False
            self._decrypt_at = now
            self._decrypt_port = port
            return False
        if (
            self._decrypt_ok is True
            and getattr(self, "_decrypt_port", None) == port
            and (now - self._decrypt_at) < _DECRYPT_TTL
        ):
            return True
        if (
            self._decrypt_ok is False
            and getattr(self, "_decrypt_port", None) == port
            and (now - self._decrypt_at) < _DECRYPT_FAIL_TTL
        ):
            return False
        ca = cert_path()
        if not port_listening(host, port) or not ca.is_file():
            self._decrypt_ok = False
            self._decrypt_at = now
            self._decrypt_port = port
            return False
        ok = await asyncio.to_thread(self._tls_via_connect, host, port, str(ca))
        if not ok:
            try:
                await self.ensure_cert(force=True)
                ca = cert_path()
                ok = await asyncio.to_thread(self._tls_via_connect, host, port, str(ca))
            except Exception:
                ok = False
        self._decrypt_ok = bool(ok)
        self._decrypt_at = now
        self._decrypt_port = port
        return bool(ok)

    def _tls_via_connect(self, proxy_host: str, proxy_port: int, ca_file: str) -> bool:
        """CONNECT 后用我们的 CA 校验 MITM 伪造证书，证明不是裸隧道。"""
        sock = None
        ssock = None
        try:
            sock = socket.create_connection((proxy_host, int(proxy_port)), timeout=8.0)
            sock.settimeout(8.0)
            sock.sendall(b"CONNECT ipv4.icanhazip.com:443 HTTP/1.1\r\nHost: ipv4.icanhazip.com:443\r\n\r\n")
            buf = b""
            while b"\r\n\r\n" not in buf and len(buf) < 4096:
                chunk = sock.recv(256)
                if not chunk:
                    break
                buf += chunk
            head = buf.split(b"\r\n", 1)[0].decode("latin1", "replace")
            if "200" not in head:
                return False
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.load_verify_locations(cafile=ca_file)
            ssock = ctx.wrap_socket(sock, server_hostname="ipv4.icanhazip.com")
            cert = ssock.getpeercert()
            sock = None
            return bool(cert)
        except ssl.SSLCertVerificationError:
            # 证书在，但校验失败：仍可能是 MITM 用了另一套 CA
            return False
        except Exception:
            return False
        finally:
            for s in (ssock, sock):
                if s is not None:
                    try:
                        s.close()
                    except Exception:
                        pass

    async def hunter_tool_defs(self, *, objective: str | None, project: dict | None) -> list[dict[str, Any]]:
        if not should_use_yakit(objective, project):
            return []
        tools = await mcp_client.list_tools(ttl=6.0)
        out: list[dict[str, Any]] = []
        for t in tools:
            name = str(t.get("name") or "")
            if not name or name in HIDDEN_TOOLS:
                continue
            schema = t.get("inputSchema") or t.get("input_schema") or {"type": "object", "properties": {}}
            out.append({
                "name": name,
                "description": str(t.get("description") or name),
                "inputSchema": schema,
            })
        return out

    def _schema_for(self, name: str) -> dict | None:
        for t in mcp_client.tools:
            if t.get("name") == name:
                s = t.get("inputSchema") or t.get("input_schema")
                return s if isinstance(s, dict) else None
        return None

    async def hunter_call(
        self,
        name: str,
        arguments: dict[str, Any] | None,
        *,
        objective: str | None,
        project: dict | None,
        scope_check,
    ) -> dict[str, Any]:
        if name in HIDDEN_TOOLS:
            return {"content": [{"type": "text", "text": "mcp_auth 不向从者暴露"}], "is_error": True}
        if not should_use_yakit(objective, project):
            return {"content": [{"type": "text", "text": "Yakit 未对当前赛道启用"}], "is_error": True}
        args = dict(arguments or {})
        why = None
        try:
            hosts: list[str] = []
            _walk_hosts(args, hosts)
            seen: set[str] = set()
            now_m = time.monotonic()
            for h in hosts:
                if h in seen:
                    continue
                seen.add(h)
                if h in ("127.0.0.1", "localhost", "::1"):
                    continue
                key = h.lower()
                ok_at = self._scope_ok.get(key, 0.0)
                if now_m - ok_at < _SCOPE_HOST_TTL:
                    continue
                why = scope_check(f"http://{h}/")
                if why:
                    break
                self._scope_ok[key] = now_m
        except Exception:
            why = None
        if why:
            return {"content": [{"type": "text", "text": f"越界：{why}"}], "is_error": True}

        if name == "start_mitm_v2":
            await self.ensure_mitm()
            if pool.must_proxy(objective) and not self.verified_exit_ip:
                return {"content": [{"type": "text", "text": self.last_error or NO_DIRECT_MSG}], "is_error": True}
            host, port = mitm_listen()
            snap = {
                "status": "reused",
                "host": host,
                "port": port,
                "downstreamProxy": self.applied_downstream or "",
                "exit_ip": self.verified_exit_ip,
            }
            return {"content": [{"type": "text", "text": json.dumps(snap, ensure_ascii=False)}], "is_error": False}

        must = pool.must_proxy(objective)
        schema = self._schema_for(name)
        send = _is_send_tool(name, args, schema)
        down = self.applied_downstream if (must and self.verified_exit_ip) else ""
        if send and must and not down:
            await self.ensure_mitm()
            down = self.applied_downstream if self.verified_exit_ip else ""
        if send and must and not down:
            return {"content": [{"type": "text", "text": self.last_error or NO_DIRECT_MSG}], "is_error": True}
        if send:
            proxy_url = down if must else ""
            _force_proxy_fields(args, proxy_url, mitm=False)
            if name == "http_fuzzer":
                args["noSystemProxy"] = True
                if must:
                    args["proxy"] = down
            if name in ("web_crawler", "create_web_fuzzer_tab", "update_web_fuzzer_tab") and must:
                args["proxy"] = down

        result = await mcp_client.call_tool(name, args)
        text = _content_text(result) or json.dumps(result, ensure_ascii=False)[:4000]
        return {
            "content": [{"type": "text", "text": text}],
            "is_error": bool(result.get("isError") or result.get("is_error")),
        }

    async def status(self, *, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force and self._status_cache and (now - self._status_at) < _STATUS_TTL:
            return self._status_cache
        engine_ready = False
        tools_count = 0
        engine_err = mcp_client.last_error
        try:
            tools = await mcp_client.list_tools(ttl=3.0 if not force else 0.0)
            tools_count = len([t for t in tools if t.get("name") and t.get("name") not in HIDDEN_TOOLS])
            engine_ready = bool(mcp_client.session_id) and engine_err is None
            if tools_count == 0 and mcp_client.session_id:
                engine_ready = True
        except Exception as e:
            engine_err = str(e)[:200]
            engine_ready = False
        mcp_url = mcp_client.url or settings_mcp_url()
        mcp_host, mcp_port = mcp_host_port(mcp_url)
        host, port = mitm_listen()
        listening = self.our_mitm_listening()
        cert = _openssl_cert_info(cert_path())
        decrypt = False
        if cert.get("readable") and not cert.get("expired") and listening:
            try:
                decrypt = await self._https_decrypt_ok()
            except Exception:
                decrypt = False
        cert_ready = bool(cert.get("readable") and not cert.get("expired") and decrypt)
        if not cert.get("exists"):
            cert_ready = False
        cert_err = None
        if not cert_ready:
            if not cert.get("exists"):
                cert_err = "证书未安装"
            elif cert.get("error"):
                cert_err = cert.get("error")
            elif not listening:
                cert_err = "等待本桥 MITM 校验证书"
            else:
                cert_err = "当前引擎 CA 与 MITM 叶子证不匹配"
        snap = {
            "enabled": bool(self.enabled),
            "engine": {
                "ready": engine_ready,
                "label": "Yakit 就绪" if engine_ready else "Yakit 未就绪",
                "url": mcp_url,
                "host": mcp_host,
                "port": mcp_port,
                "name": mcp_client.server_name or "Yaklang MCP",
                "error": None if engine_ready else (engine_err or "无法 tools/list"),
            },
            "cert": {
                "ready": cert_ready,
                "label": "证书就绪" if cert_ready else "证书异常",
                "path": cert.get("path"),
                "fingerprint": cert.get("fingerprint") or "",
                "expires_at": cert.get("expires_at") or "",
                "expired": bool(cert.get("expired")),
                "decrypt_ok": decrypt,
                "error": None if cert_ready else cert_err,
            },
            "mitm": {
                "listening": listening,
                "host": host,
                "port": port,
                "downstream": self.applied_downstream or "",
                "verified": bool(self.verified_exit_ip),
                "exit_ip": self.verified_exit_ip,
            },
            "backup_text": self.backup_text,
            "last_good_proxy": self.last_good_proxy,
            "tools_count": tools_count,
            "oob_ready": bool(getattr(mcp_client, "has_oob", False)),
            "error": self.last_error,
        }
        self._status_cache = snap
        self._status_at = time.monotonic()
        return snap


yakit = YakitBridge()
yakit.load()
