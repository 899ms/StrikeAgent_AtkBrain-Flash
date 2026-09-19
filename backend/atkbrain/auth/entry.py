"""随机安全入口：8 位路径，未带前缀则本机展示产品介绍页（不跳转）。"""
from __future__ import annotations

import mimetypes
import os
import secrets
from pathlib import Path
from typing import Any

from ..config import settings

ENTRY_LEN = 8
# 去掉 0OIl1 等易混字符。
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LOOPBACK = frozenset({"127.0.0.1", "::1", "testclient", "localhost"})
_DECOY_DIR = Path(__file__).resolve().parent.parent / "decoy_web"
_EXTRA_MIME = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".html": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def _entry_path() -> Path:
    return Path(settings.data_dir) / "security_entry"


def entry_disabled() -> bool:
    raw = str(getattr(settings, "security_entry", "") or "").strip().lower()
    return raw in ("off", "0", "false", "no", "disable", "disabled")


def _sanitize_entry(raw: str) -> str:
    s = "".join(ch for ch in str(raw or "").strip().strip("/") if ch.isalnum())
    return s[:32]


def _generate() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(ENTRY_LEN))


def load_or_create_entry() -> str:
    """持久化入口。已有文件不改；禁止用环境变量指定路径（只能 off 关掉）。"""
    if entry_disabled():
        return ""
    path = _entry_path()
    if path.is_file():
        got = _sanitize_entry(path.read_text(encoding="utf-8"))
        if len(got) >= 4:
            return got
    token = _generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(token + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)
    return token


def security_entry() -> str:
    """只读已持久化的入口；没有文件时返回空（不读环境变量、不在读路径上生成）。"""
    if entry_disabled():
        return ""
    path = _entry_path()
    if path.is_file():
        got = _sanitize_entry(path.read_text(encoding="utf-8"))
        if len(got) >= 4:
            return got
    return ""


def entry_prefix() -> str:
    token = security_entry()
    return f"/{token}" if token else ""


def cookie_path_prefix() -> str:
    p = entry_prefix()
    return f"{p}/" if p else "/"


def peer_host(scope_or_request: Any) -> str:
    """只用 TCP 对端，不信 X-Forwarded-For。"""
    if isinstance(scope_or_request, dict):
        client = scope_or_request.get("client")
        if client and len(client) >= 1:
            return str(client[0] or "")
        return ""
    client = getattr(scope_or_request, "client", None)
    if client is not None and getattr(client, "host", None):
        return str(client.host)
    scope = getattr(scope_or_request, "scope", None)
    if isinstance(scope, dict):
        c = scope.get("client")
        if c and len(c) >= 1:
            return str(c[0] or "")
    return ""


def is_loopback_peer(host: str) -> bool:
    h = (host or "").strip().lower()
    if h in _LOOPBACK:
        return True
    if h.startswith("127."):
        return True
    if h == "::ffff:127.0.0.1":
        return True
    return False


def path_has_entry(path: str, token: str | None = None) -> bool:
    tok = token if token is not None else security_entry()
    if not tok:
        return True
    p = path or "/"
    prefix = "/" + tok
    return p == prefix or p.startswith(prefix + "/")


def strip_entry_path(path: str, token: str | None = None) -> str:
    tok = token if token is not None else security_entry()
    if not tok:
        return path or "/"
    prefix = "/" + tok
    p = path or "/"
    if p == prefix:
        return "/"
    if p.startswith(prefix + "/"):
        rest = p[len(prefix):]
        return rest if rest else "/"
    return p


def rewrite_scope_entry(scope: dict) -> bool:
    """命中入口则剥前缀。返回是否允许继续。关入口时全放行。回环不再旁路（:2334 socat 对端也是 127.0.0.1）。"""
    if scope.get("type") not in ("http", "websocket"):
        return True
    if entry_disabled():
        return True
    token = security_entry()
    if not token:
        return True
    path = scope.get("path") or "/"
    if not path_has_entry(path, token):
        return False
    _apply_strip(scope, token)
    return True


def _apply_strip(scope: dict, token: str) -> None:
    path = scope.get("path") or "/"
    if not path_has_entry(path, token):
        return
    new = strip_entry_path(path, token)
    prefix = "/" + token
    scope["path"] = new
    raw = scope.get("raw_path")
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw_s = raw.decode("latin-1")
        except Exception:
            raw_s = path
        if raw_s.startswith(prefix):
            rest = raw_s[len(prefix):] or "/"
            scope["raw_path"] = rest.encode("latin-1")
    # 不要写 root_path：Starlette StaticFiles 假定 path 仍含 root_path 前缀，
    # 再叠一层会把 /assets/x.js 解析成 dist/assets/assets/x.js 而 404。
    # 前端靠 <base href> 与 __ATKBRAIN_BASE__，不靠 ASGI root_path。


def decoy_file(url_path: str) -> Path | None:
    """无入口只给介绍页根路径和它的静态文件，不把任意 URL 回落到 index.html。"""
    root = _DECOY_DIR.resolve()
    raw = (url_path or "/").split("?", 1)[0]
    if raw in ("", "/"):
        idx = root / "index.html"
        return idx if idx.is_file() else None
    rel = raw.lstrip("/")
    if not rel or rel.endswith("/") or "\\" in rel:
        return None
    if rel in ("favicon.svg", "favicon.ico"):
        p = root / rel
        return p if p.is_file() else None
    if rel.startswith("assets/") and rel.count("/") == 1:
        name = rel.split("/", 1)[1]
        if not name or name in (".", ".."):
            return None
        p = (root / "assets" / name).resolve()
        try:
            p.relative_to(root / "assets")
        except ValueError:
            return None
        return p if p.is_file() else None
    return None


def _decoy_content_type(path: Path) -> str:
    extra = _EXTRA_MIME.get(path.suffix.lower())
    if extra:
        return extra
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


async def _send_decoy(scope: dict, send: Any) -> None:
    path = decoy_file(str(scope.get("path") or "/"))
    if path is None:
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [
                (b"content-type", b"text/html; charset=utf-8"),
                (b"cache-control", b"no-store, no-cache, must-revalidate"),
                (b"x-content-type-options", b"nosniff"),
                (b"content-length", b"0"),
            ],
        })
        await send({"type": "http.response.body", "body": b""})
        return
    try:
        body = path.read_bytes()
    except OSError:
        body = b""
    ctype = _decoy_content_type(path).encode("ascii")
    headers = [
        (b"content-type", ctype),
        (b"cache-control", b"no-store, no-cache, must-revalidate"),
        (b"x-content-type-options", b"nosniff"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    method = (scope.get("method") or "GET").upper()
    await send({"type": "http.response.start", "status": 200, "headers": headers})
    await send({"type": "http.response.body", "body": b"" if method == "HEAD" else body})


class SecurityEntryMiddleware:
    """ASGI：HTTP 与 WebSocket 都过入口。"""

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        if rewrite_scope_entry(scope):
            await self.app(scope, receive, send)
            return
        if scope.get("type") == "websocket":
            try:
                await send({"type": "websocket.close", "code": 4404})
            except Exception:
                pass
            return
        await _send_decoy(scope, send)


def public_console_url(*, host: str | None = None, port: int | None = None) -> str:
    h = (host or guess_lan_ip() or "127.0.0.1").strip()
    try:
        p = int(port if port is not None else getattr(settings, "frontend_port", 2334) or 2334)
    except (TypeError, ValueError):
        p = 2334
    prefix = entry_prefix()
    return f"http://{h}:{p}{prefix}/login"


def guess_lan_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = str(s.getsockname()[0] or "")
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"
