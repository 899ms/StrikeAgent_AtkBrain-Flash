"""公网强制 HTTPS：应用仍听 HTTP，跳到反代的 https 源。"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse

from ..config import settings
from .cookies import cookie_secure


def https_redirect_target(request: Request) -> str | None:
    """需要跳转时返回绝对 https URL；否则 None。回环探活不跳。"""
    if not bool(getattr(settings, "force_https", False)):
        return None
    if cookie_secure(request):
        return None
    from .entry import is_loopback_peer, peer_host
    if is_loopback_peer(peer_host(request)):
        return None
    origin = str(getattr(settings, "public_origin", "") or "").strip().rstrip("/")
    if origin.lower().startswith("https://"):
        base = origin
    else:
        host = (request.headers.get("host") or request.url.hostname or "").split(":")[0].strip()
        if not host:
            return None
        base = f"https://{host}:2334"
    path = request.url.path or "/"
    query = request.url.query
    url = base + path
    if query:
        url += "?" + query
    return url


def https_redirect_response(request: Request) -> RedirectResponse | None:
    target = https_redirect_target(request)
    if not target:
        return None
    return RedirectResponse(target, status_code=301)
