"""python -m atkbrain.panel — 打印控制台入口 URL 与可读取的口令。"""
from __future__ import annotations

import asyncio


def _print_info() -> None:
    from .auth.bootstrap import read_bootstrap_secret
    from .auth.entry import entry_prefix, load_or_create_entry, public_console_url, security_entry
    from .auth.store import any_user
    from .config import settings

    load_or_create_entry()

    async def _user():
        from .db import db
        await db.connect()
        try:
            return await any_user()
        finally:
            await db.close()

    row = None
    try:
        row = asyncio.run(_user())
    except Exception:
        row = None
    user = str((row or {}).get("username") or getattr(settings, "admin_user", None) or "admin")
    bootstrap_done = False
    try:
        bootstrap_done = int((row or {}).get("bootstrap_login_done") or 0) != 0
    except (TypeError, ValueError):
        bootstrap_done = False
    secret = read_bootstrap_secret()
    token = security_entry()
    url = public_console_url()
    print("==================================================================")
    print("StrikeAgent_AtkBrain-Flash")
    print("==================================================================")
    print(f"URL:      {url}")
    print(f"Entry:    {entry_prefix() or '(disabled)'}")
    print(f"Username: {user}")
    if not bootstrap_done:
        print("Password: admin  (仅第一次登录有效；登录后默认口令失效)")
        if secret and secret != "admin":
            print(f"          本机副本: {secret}")
    elif secret:
        print(f"Password: {secret}")
        print("          （仅本机 0600，网页/API 读不到；有这台机器的 shell 即可查看）")
    else:
        print("Password: 本机没有明文副本（改密发生在此功能之前，哈希不可逆）")
        print("          在设置里再改一次口令，或 ATKBRAIN_ADMIN_PASSWORD_RESET=1 后重启")
        print("          之后本命令即可打印。")
    print("------------------------------------------------------------------")
    print("忘记入口或口令时，在这台机器上执行：")
    print("  Docker：docker compose exec atkbrain python -m atkbrain.panel")
    print("          （或仓库根目录 scripts/atkbrain-panel.sh，有容器时会自动进容器）")
    print("  systemd：scripts/atkbrain-panel.sh")
    print("           或 cd backend && python3 -m atkbrain.panel")
    if not token:
        print("安全入口已关闭（ATKBRAIN_SECURITY_ENTRY=off）。")
    print("==================================================================")


def main() -> None:
    _print_info()


if __name__ == "__main__":
    main()
