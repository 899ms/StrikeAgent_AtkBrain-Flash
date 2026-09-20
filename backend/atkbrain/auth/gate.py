"""请求是否已通过会话 Cookie 或 API Token。"""
from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request, WebSocket

from ..config import settings
from .bootstrap import env_no_auth, login_required
from .cookies import COOKIE_NAME
from .store import get_session, touch_session, user_by_id, user_flag


def client_ip(request: Request | WebSocket) -> str:
    """限流用。入口判定不要用这个（会信 X-Forwarded-For）。"""
    forwarded = ""
    if isinstance(request, Request):
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if forwarded:
            return forwarded[:64]
        if request.client and request.client.host:
            return str(request.client.host)
        return "0.0.0.0"
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:64]
    if request.client and request.client.host:
        return str(request.client.host)
    return "0.0.0.0"


def extract_api_token(request: Request | WebSocket) -> str:
    if isinstance(request, Request):
        h = (request.headers.get("x-api-token") or "").strip()
        if h:
            return h
        auth = (request.headers.get("authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return ""
    hdr = (request.headers.get("x-api-token") or "").strip()
    if hdr:
        return hdr
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def cookie_token(request: Request | WebSocket) -> str:
    if isinstance(request, Request):
        return (request.cookies.get(COOKIE_NAME) or "").strip()
    return (request.cookies.get(COOKIE_NAME) or "").strip()


async def session_from_request(request: Request | WebSocket) -> dict | None:
    raw = cookie_token(request)
    sess = await get_session(raw)
    if not sess:
        return None
    await touch_session(sess["id"])
    user = await user_by_id(str(sess.get("user_id") or ""))
    if not user:
        return None
    return {"session": sess, "user": user, "token": raw}


async def api_token_ok(request: Request | WebSocket) -> bool:
    expected = (settings.api_token or "").strip()
    if not expected:
        return False
    got = extract_api_token(request)
    if not got:
        return False
    return secrets_compare(got, expected)


def secrets_compare(a: str, b: str) -> bool:
    import hmac
    aa = (a or "").encode("utf-8")
    bb = (b or "").encode("utf-8")
    if len(aa) != len(bb):
        hmac.compare_digest(aa, aa)
        return False
    return hmac.compare_digest(aa, bb)


async def auth_ok(request: Request | WebSocket) -> bool:
    if env_no_auth():
        return True
    if await session_from_request(request):
        return True
    if await api_token_ok(request):
        return True
    if not await login_required():
        expected = (settings.api_token or "").strip()
        return not expected
    return False


def _host_name(value: str) -> str:
    """Origin netloc 与 Host 比主机名；反代常把 Host 写成无端口。"""
    h = (value or "").strip().lower()
    if h.startswith("["):
        end = h.find("]")
        if end > 0:
            return h[: end + 1]
        return h
    if h.count(":") == 1:
        return h.split(":", 1)[0]
    return h


def origin_ok(request: Request) -> bool:
    """Cookie 登录/改密：有 Origin/Referer 时必须对上 Host 或 CORS 列表。"""
    origin = (request.headers.get("origin") or "").strip()
    referer = (request.headers.get("referer") or "").strip()
    host = (request.headers.get("host") or "").strip().lower()
    if not origin and not referer:
        return True

    def netloc(url: str) -> str:
        return (urlparse(url).netloc or "").lower()

    got = netloc(origin) if origin else netloc(referer)
    if not got:
        return True
    if host and (got == host or _host_name(got) == _host_name(host)):
        return True
    for item in str(getattr(settings, "cors_origins", "") or "").split(","):
        item = item.strip()
        if not item:
            continue
        if item and netloc(item) == got:
            return True
    return False


def must_change_path_allowed(path: str) -> bool:
    p = path or ""
    return p in (
        "/api/auth/me",
        "/api/auth/logout",
        "/api/auth/password",
        "/api/auth/pubkey",
    )


def auth_public_path(path: str) -> bool:
    return (path or "") in (
        "/api/auth/me",
        "/api/auth/pubkey",
        "/api/auth/login",
        "/api/auth/logout",
    )


def session_must_change(sess: dict | None) -> bool:
    user = (sess or {}).get("user") if sess else None
    return user_flag(user, "must_change_password")
