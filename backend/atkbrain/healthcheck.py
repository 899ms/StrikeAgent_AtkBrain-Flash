"""本机探活：带随机入口访问 /api/health。供 Docker/systemd 使用，不走网页。"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request


def _url() -> str:
    from .auth.entry import entry_disabled, security_entry
    from .config import settings

    try:
        port = int(getattr(settings, "port", 2333) or 2333)
    except (TypeError, ValueError):
        port = 2333
    prefix = ""
    if not entry_disabled():
        tok = (security_entry() or "").strip()
        if tok:
            prefix = "/" + tok
    return f"http://127.0.0.1:{port}{prefix}/api/health"


def main() -> None:
    url = _url()
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            raw = resp.read()
            if int(getattr(resp, "status", 200) or 200) >= 400:
                sys.exit(1)
            sys.stdout.buffer.write(raw)
    except (urllib.error.URLError, TimeoutError, OSError):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
