"""登录与中间件共用的 Cookie 属性，避免标志漂移。"""
from __future__ import annotations

import time

from fastapi import Request, Response

from ..config import settings

COOKIE_NAME = "atkbrain_session"
DEFAULT_SESSION_TTL_SEC = 24 * 3600


def session_ttl_sec() -> int:
    try:
        n = int(getattr(settings, "session_max_age_sec", 0) or DEFAULT_SESSION_TTL_SEC)
    except (TypeError, ValueError):
        n = DEFAULT_SESSION_TTL_SEC
    return n if n > 0 else DEFAULT_SESSION_TTL_SEC


def remaining_cookie_max_age(expires_at: float | None) -> int:
    """浏览器 Cookie 只跟会话绝对过期对齐，不再每次请求重置成满窗口。"""
    if expires_at is None:
        return session_ttl_sec()
    try:
        left = int(float(expires_at) - time.time())
    except (TypeError, ValueError):
        return 0
    return max(0, left)


def cookie_secure(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    return proto.lower() == "https"


def cookie_kwargs(request: Request, *, max_age: int | None = None) -> dict:
    ttl = session_ttl_sec() if max_age is None else int(max_age)
    if ttl < 0:
        ttl = 0
    path = "/"
    try:
        from .entry import cookie_path_prefix, entry_disabled
        if not entry_disabled():
            path = cookie_path_prefix() or "/"
    except Exception:
        path = "/"
    return {
        "key": COOKIE_NAME,
        "max_age": ttl,
        "httponly": True,
        "samesite": "lax",
        "secure": cookie_secure(request),
        "path": path,
    }


def apply_session_cookie(
    response: Response,
    token: str,
    request: Request,
    *,
    expires_at: float | None = None,
) -> None:
    extra: dict = {}
    if expires_at is not None:
        extra["max_age"] = remaining_cookie_max_age(expires_at)
    kw = cookie_kwargs(request, **extra)
    response.set_cookie(value=token, **kw)


def clear_session_cookie(response: Response, request: Request) -> None:
    kw = cookie_kwargs(request)
    path = str(kw.get("path") or "/")
    kw["max_age"] = 0
    response.set_cookie(value="", **kw)
    response.delete_cookie(COOKIE_NAME, path=path)
    if path != "/":
        response.delete_cookie(COOKIE_NAME, path="/")
