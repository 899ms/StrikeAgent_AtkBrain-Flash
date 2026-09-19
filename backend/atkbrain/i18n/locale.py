"""Normalize zh|en and request-scoped locale."""
from __future__ import annotations

from contextvars import ContextVar

_locale: ContextVar[str] = ContextVar("atkbrain_locale", default="zh")
_report_lang: ContextVar[str] = ContextVar("atkbrain_report_lang", default="zh")


def normalize_locale(raw: object) -> str:
    s = str(raw or "").strip().lower().replace("_", "-")
    if s.startswith("en"):
        return "en"
    return "zh"


def set_locale(raw: object) -> str:
    lang = normalize_locale(raw)
    _locale.set(lang)
    return lang


def get_locale() -> str:
    return normalize_locale(_locale.get())


def set_report_lang(raw: object) -> str:
    lang = normalize_locale(raw)
    _report_lang.set(lang)
    return lang


def get_report_lang() -> str:
    return normalize_locale(_report_lang.get())


def config_output_lang(cfg: object) -> str:
    if isinstance(cfg, str):
        try:
            import json
            cfg = json.loads(cfg)
        except Exception:
            cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    return normalize_locale(cfg.get("output_lang"))


def locale_from_request(request) -> str:
    header = ""
    try:
        header = request.headers.get("x-locale") or request.headers.get("accept-language") or ""
    except Exception:
        header = ""
    if "," in header:
        header = header.split(",", 1)[0]
    if ";" in header:
        header = header.split(";", 1)[0]
    return normalize_locale(header)
