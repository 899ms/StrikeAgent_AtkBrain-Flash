"""登录/验证码按 IP、用户名计数；锁进 SQLite，重启清不掉。"""
from __future__ import annotations

import time

from ..db import db

FAIL_LIMIT_USER = 5
FAIL_WINDOW_USER = 15 * 60
LOCK_USER = 15 * 60
FAIL_LIMIT_IP = 20
FAIL_WINDOW_IP = 60 * 60
LOCK_IP = 60 * 60


def _now() -> float:
    return time.time()


async def locked_until(key: str) -> float:
    row = await db.fetchone("SELECT locked_until FROM auth_lockouts WHERE key=?", (key,))
    if not row:
        return 0.0
    until = float(row.get("locked_until") or 0)
    return until if until > _now() else 0.0


async def assert_not_locked(*keys: str) -> float:
    latest = 0.0
    for k in keys:
        until = await locked_until(k)
        latest = max(latest, until)
    if latest > _now():
        return latest
    return 0.0


async def record_fail(key: str, *, limit: int, window: float, lock_for: float) -> float:
    now = _now()
    row = await db.fetchone("SELECT fails, window_start, locked_until FROM auth_lockouts WHERE key=?", (key,))
    if row and float(row.get("locked_until") or 0) > now:
        return float(row["locked_until"])
    fails = 0
    start = now
    if row:
        start = float(row.get("window_start") or now)
        fails = int(row.get("fails") or 0)
        if now - start > window:
            fails = 0
            start = now
    fails += 1
    until = 0.0
    if fails >= limit:
        until = now + lock_for
        fails = 0
        start = now
    await db.execute(
        """INSERT INTO auth_lockouts(key, fails, window_start, locked_until)
           VALUES(?,?,?,?)
           ON CONFLICT(key) DO UPDATE SET
             fails=excluded.fails,
             window_start=excluded.window_start,
             locked_until=excluded.locked_until""",
        (key, fails, start, until),
    )
    return until


async def record_login_fail(ip: str, username: str) -> float:
    a = await record_fail(f"ip:{ip}", limit=FAIL_LIMIT_IP, window=FAIL_WINDOW_IP, lock_for=LOCK_IP)
    b = await record_fail(
        f"user:{(username or '').strip().lower()}",
        limit=FAIL_LIMIT_USER, window=FAIL_WINDOW_USER, lock_for=LOCK_USER,
    )
    return max(a, b)


async def clear_fails(*keys: str) -> None:
    for k in keys:
        await db.execute("DELETE FROM auth_lockouts WHERE key=?", (k,))
