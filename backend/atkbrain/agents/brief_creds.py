"""题面已出现的账密字面量。只摘录，不合成、不按厂商名拼默认口令。"""
from __future__ import annotations

import re

# 进程健康检查用：旧进程没有这个字段。
CREDS_MODE = "literal_only"

_EXPLICIT_PAIR_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9._-]{1,20})\s*(?:[:/=])\s*"
    r"([A-Za-z0-9@._!#$%^*+-]{3,32})\b"
)
_LEAKED_PASS_RE = re.compile(
    r"(?i)(?:password|passwd|口令)\s*[=:]\s*['\"]?"
    r"([A-Za-z0-9@._!#$%^*+-]{3,32})"
)
_USER_STOP = frozenset({
    "http", "https", "www", "ftp", "ssh", "tcp", "udp", "api", "url",
})
_PASS_STOP = frozenset({
    "http", "https", "html", "com", "org", "net", "php", "asp", "jsp",
})


def graph_cred_blob(graph: dict | None, limit: int = 3000) -> str:
    """图节点正文，供摘录已经写在图上的账密字面量。"""
    parts: list[str] = []
    for n in (graph or {}).get("nodes") or []:
        if not isinstance(n, dict):
            continue
        blob = f"{n.get('title') or ''} {n.get('detail') or ''}".strip()
        if blob:
            parts.append(blob)
    return "\n".join(parts)[: max(0, int(limit or 0) or 3000)]


def _explicit_pairs(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in _EXPLICIT_PAIR_RE.finditer(text or ""):
        user, pw = m.group(1), m.group(2)
        if user.lower() in _USER_STOP or pw.lower() in _PASS_STOP:
            continue
        if "//" in f"{user}/{pw}" or user.lower() in {"http", "https"}:
            continue
        key = f"{user}/{pw}".lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(f"{user}/{pw}")
    return out[:6]


def _leaked_secrets(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in _LEAKED_PASS_RE.finditer(text or ""):
        pw = (m.group(1) or "").strip()
        if not pw or pw.lower() in _PASS_STOP or pw.lower() in seen:
            continue
        seen.add(pw.lower())
        out.append(pw)
    return out[:6]


def credential_candidates_from_brief(text: str, max_pairs: int = 10) -> list[str]:
    """只返回正文里已经出现的 user/pass 或 password= 字面量。禁止合成。"""
    blob = (text or "").strip()
    if not blob:
        return []
    limit = max(1, min(int(max_pairs or 10), 10))
    out: list[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        s = (item or "").strip()
        if not s or s.lower() in seen:
            return
        seen.add(s.lower())
        out.append(s)

    for p in _explicit_pairs(blob):
        add(p)
    for p in _leaked_secrets(blob):
        add(p)
    return out[:limit]


def format_cred_hint(cands: list[str] | None) -> str:
    items = [str(x).strip() for x in (cands or []) if str(x).strip()]
    if not items:
        return ""
    return "；题面已出现的账密（禁止合成、禁止扩字典）：" + "、".join(items[:8])


def password_values(cands: list[str] | None) -> set[str]:
    """user/pass 对里的口令，以及单独出现的 password= 字面量。"""
    out: set[str] = set()
    for raw in cands or []:
        s = str(raw or "").strip()
        if not s:
            continue
        out.add(s.lower())
        if "/" in s:
            out.add(s.split("/", 1)[-1].lower())
    return out


_SSHPASS_P_RE = re.compile(
    r"\bsshpass\b(?:\s+-\w)*\s+-p\s*(?:'([^']*)'|\"([^\"]*)\"|(\S+))",
    re.I,
)


def sshpass_password_from_cmd(command: str) -> str | None:
    m = _SSHPASS_P_RE.search(command or "")
    if not m:
        return None
    return (m.group(1) or m.group(2) or m.group(3) or "").strip() or None
