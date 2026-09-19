"""二次验证 / 红队评级自动任务开关。持久化在 proxy-settings.json，缺键当开。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..proxy.pool import _merge_settings, _settings_path

KEY_SECONDARY = "finding_secondary_verify"
KEY_RATING = "finding_redteam_rating"


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default


def _read_settings() -> dict[str, Any]:
    p: Path = _settings_path()
    if not p.is_file():
        return {}
    try:
        loaded = json.loads(p.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def get_review_flags() -> dict[str, bool]:
    data = _read_settings()
    return {
        "secondary_verify": _as_bool(data.get(KEY_SECONDARY), True),
        "redteam_rating": _as_bool(data.get(KEY_RATING), True),
    }


def set_review_flags(
    *,
    secondary_verify: bool | None = None,
    redteam_rating: bool | None = None,
) -> dict[str, bool]:
    updates: dict[str, Any] = {}
    if secondary_verify is not None:
        updates[KEY_SECONDARY] = bool(secondary_verify)
    if redteam_rating is not None:
        updates[KEY_RATING] = bool(redteam_rating)
    if updates:
        _merge_settings(updates)
    return get_review_flags()
