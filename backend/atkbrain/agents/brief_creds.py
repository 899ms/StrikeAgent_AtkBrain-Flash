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
    r"(?i)(?:password|passwd|口令|密码)\s*[=:]\s*['\"]?"
    r"([A-Za-z0-9@._!#$%^*+-]{3,200})"
)
_USER_LABELED_RE = re.compile(
    r"(?i)(?:\buser(?:name)?\b|账号|用户名|账户)\s*[:=]\s*['\"]?"
    r"([A-Za-z0-9._@+-]{1,80})"
)
_USER_CN_SPACE_RE = re.compile(
    r"(?:账号|用户名|账户)\s+([A-Za-z0-9._@+-]{1,80})"
)
_PASS_CN_SPACE_RE = re.compile(
    r"(?:密码|口令)\s+([^\s]{3,200})"
)
_BEARER_RE = re.compile(
    r"(?i)(?:authorization\s*[:=]\s*)?bearer\s+"
    r"([A-Za-z0-9._\-+=/]{8,})"
)
_COOKIE_RE = re.compile(r"(?i)\bcookie\s*[:=]\s*(.+)$", re.M)
_API_KEY_RE = re.compile(
    r"(?i)(?:\bapi[_-]?key\b|\baccess[_-]?token\b|\bx-api-key\b|\bjwt\b)"
    r"\s*[:=]\s*['\"]?(\S{6,})"
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_AUTHZ_RE = re.compile(r"(?i)authorization\s*[:=]\s*(.+)$", re.M)
_BENCH_CTX_RE = re.compile(r"(?i)benchmark")
_USER_MAX = 200
_PASS_MAX = 500
_TOKEN_MAX = 8000
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
    for p in _token_literals(blob):
        add(p)
    return out[:limit]


def format_cred_hint(cands: list[str] | None) -> str:
    items = [str(x).strip() for x in (cands or []) if str(x).strip()]
    if not items:
        return ""
    return "；题面已出现的账密（禁止合成、禁止扩字典）：" + "、".join(items[:8])


def password_values(cands: list[str] | None) -> set[str]:
    """user/pass 对里的口令，以及单独出现的 password= / Bearer / Cookie 字面量。"""
    out: set[str] = set()
    for raw in cands or []:
        s = str(raw or "").strip()
        if not s:
            continue
        low = s.lower()
        out.add(low)
        if "/" in s and not low.startswith(("http://", "https://", "bearer ", "cookie:")):
            out.add(s.split("/", 1)[-1].lower())
        if low.startswith("bearer "):
            out.add(s.split(None, 1)[-1].lower())
        if low.startswith("cookie:"):
            out.add(s.split(":", 1)[-1].strip().lower())
        if low.startswith("authorization:"):
            rest = s.split(":", 1)[-1].strip()
            out.add(rest.lower())
            if rest.lower().startswith("bearer "):
                out.add(rest.split(None, 1)[-1].lower())
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


def _clip(val: str, n: int) -> str:
    s = (val or "").strip().strip("'\"")
    if not s:
        return ""
    return s[: max(1, int(n or 1))]


def _token_literals(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        s = (item or "").strip().rstrip(",;")
        if len(s) < 8 or s.lower() in seen or _BENCH_CTX_RE.search(s):
            return
        seen.add(s.lower())
        out.append(s)

    blob = text or ""
    for m in _BEARER_RE.finditer(blob):
        add("Bearer " + (m.group(1) or "").strip())
    for m in _COOKIE_RE.finditer(blob):
        add("Cookie: " + (m.group(1) or "").strip())
    for m in _API_KEY_RE.finditer(blob):
        add((m.group(1) or "").strip())
    for m in _JWT_RE.finditer(blob):
        add(m.group(0) or "")
    for m in _AUTHZ_RE.finditer(blob):
        rest = (m.group(1) or "").strip()
        if rest.lower().startswith("bearer "):
            continue
        add("Authorization: " + rest)
    return out[:8]


def normalize_supplied_auth(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}
    user = _clip(str(raw.get("user") or raw.get("username") or ""), _USER_MAX)
    password = _clip(str(raw.get("password") or raw.get("pass") or ""), _PASS_MAX)
    token = _clip(str(raw.get("token") or raw.get("auth_token") or ""), _TOKEN_MAX)
    out: dict[str, str] = {}
    if user:
        out["user"] = user
    if password:
        out["password"] = password
    if token:
        out["token"] = token
    return out


def merge_supplied_auth(existing: object, incoming: object) -> dict:
    out = normalize_supplied_auth(existing)
    src = normalize_supplied_auth(incoming)
    for k, v in src.items():
        if v:
            out[k] = v
    return out


def extract_supplied_auth(text: str) -> dict:
    """从人工句 / 简报摘 user、password、Bearer、Cookie、api_key。不碰评测 token。"""
    blob = text or ""
    if not blob.strip():
        return {}
    user = ""
    password = ""
    m = _USER_LABELED_RE.search(blob) or _USER_CN_SPACE_RE.search(blob)
    if m:
        user = _clip(m.group(1), _USER_MAX)
    m = _LEAKED_PASS_RE.search(blob) or _PASS_CN_SPACE_RE.search(blob)
    if m:
        password = _clip(m.group(1), _PASS_MAX)
    if not user or not password:
        for pair in _explicit_pairs(blob):
            if "/" not in pair:
                continue
            u, pw = pair.split("/", 1)
            if not user:
                user = _clip(u, _USER_MAX)
            if not password:
                password = _clip(pw, _PASS_MAX)
            break
    token = ""
    bm = _BEARER_RE.search(blob)
    if bm:
        token = _clip(bm.group(1), _TOKEN_MAX)
    if not token:
        cm = _COOKIE_RE.search(blob)
        if cm:
            token = _clip("Cookie: " + (cm.group(1) or "").strip(), _TOKEN_MAX)
    if not token:
        am = _API_KEY_RE.search(blob)
        if am and not _BENCH_CTX_RE.search(am.group(0) or ""):
            token = _clip(am.group(1), _TOKEN_MAX)
    if not token:
        jm = _JWT_RE.search(blob)
        if jm:
            token = _clip(jm.group(0), _TOKEN_MAX)
    if not token:
        hm = _AUTHZ_RE.search(blob)
        if hm and not _BENCH_CTX_RE.search(hm.group(0) or ""):
            token = _clip(hm.group(1), _TOKEN_MAX)
    return normalize_supplied_auth({"user": user, "password": password, "token": token})


def merge_steering_supplied_auth(existing: object, messages: list | None) -> dict:
    acc = normalize_supplied_auth(existing)
    for raw in messages or []:
        acc = merge_supplied_auth(acc, extract_supplied_auth(str(raw or "")))
    return acc


def secrets_from_supplied_auth(auth: object) -> set[str]:
    a = normalize_supplied_auth(auth)
    out: set[str] = set()
    for k in ("user", "password", "token"):
        v = str(a.get(k) or "").strip()
        if not v:
            continue
        out.add(v.lower())
        low = v.lower()
        for pfx in ("bearer ", "cookie: ", "authorization: "):
            if low.startswith(pfx):
                rest = v[len(pfx):].strip()
                if rest:
                    out.add(rest.lower())
                    if rest.lower().startswith("bearer "):
                        out.add(rest.split(None, 1)[-1].lower())
    if a.get("user") and a.get("password"):
        out.add(f"{a['user']}/{a['password']}".lower())
    return out


def format_supplied_auth_brief(auth: object, *, src: bool = False) -> str:
    a = normalize_supplied_auth(auth)
    if not a:
        return ""
    lines = [
        "授权测试身份（必须先登录或在请求头携带 Authorization/Cookie 再测越权/IDOR；"
        "禁止 hydra 施射；这些口令不当前台弱口令洞报；无请求体的空 POST 不能否证登录失败）："
    ]
    if a.get("user"):
        lines.append(f"user={a['user']}")
    if a.get("password"):
        lines.append(f"password={a['password']}")
    tok = a.get("token") or ""
    if tok:
        low = tok.lower()
        if low.startswith(("bearer ", "cookie:", "authorization:")):
            lines.append(tok)
        else:
            lines.append(f"Authorization: Bearer {tok}")
    if src:
        lines.append("给定身份只用来做授权后的读面/越权证明；禁止真改生产、禁止 getshell 收工。")
    return "\n".join(lines)
