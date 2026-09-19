"""口令策略：用户自选 ≥8 且大写+小写+数字；首登轮换为 8 位大小写字母。"""
from __future__ import annotations

import re
import secrets
import string

POLICY_MIN_LEN = 8
BOOTSTRAP_LEN = 8

_NEED_LEN = "len"
_NEED_UPPER = "upper"
_NEED_LOWER = "lower"
_NEED_DIGIT = "digit"


def password_policy_code(password: str) -> str | None:
    pw = password or ""
    if len(pw) < POLICY_MIN_LEN:
        return _NEED_LEN
    if not re.search(r"[A-Z]", pw):
        return _NEED_UPPER
    if not re.search(r"[a-z]", pw):
        return _NEED_LOWER
    if not re.search(r"[0-9]", pw):
        return _NEED_DIGIT
    return None


def password_policy_error(password: str) -> str | None:
    code = password_policy_code(password)
    return {
        _NEED_LEN: "口令至少 8 位",
        _NEED_UPPER: "口令须含大写字母",
        _NEED_LOWER: "口令须含小写字母",
        _NEED_DIGIT: "口令须含数字",
    }.get(code or "", None)


def generate_bootstrap_password(n: int = BOOTSTRAP_LEN) -> str:
    """8 位大小写字母，至少各 1 个。不含数字（与用户自选策略区分）。"""
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    alphabet = lower + upper
    size = max(4, int(n or BOOTSTRAP_LEN))
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(size))
        if any(c.islower() for c in pw) and any(c.isupper() for c in pw):
            return pw
