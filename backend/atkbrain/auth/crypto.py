"""口令哈希、会话令牌哈希、RSA-OAEP。私钥只放 data 目录。"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import secrets
import time
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ..config import settings

_PH = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
_DUMMY = _PH.hash("atkbrain-dummy-not-a-real-password")
_PRIV: rsa.RSAPrivateKey | None = None
_HMAC: bytes | None = None
BLOB_TTL_SEC = 120
BLOB_MAX_PASSWORD = 96


def hash_password(password: str) -> str:
    return _PH.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return bool(_PH.verify(encoded, password))
    except (VerifyMismatchError, InvalidHash, TypeError, ValueError):
        return False


def dummy_verify(password: str) -> None:
    """用户不存在时仍走一遍 argon2，避免计时差。"""
    try:
        _PH.verify(_DUMMY, password)
    except Exception:
        pass


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def _atomic_secret_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)


def _hmac_path() -> Path:
    return Path(settings.data_dir) / "auth-session.key"


def _hmac_key() -> bytes:
    global _HMAC
    if _HMAC is not None:
        return _HMAC
    path = _hmac_path()
    if path.is_file():
        _HMAC = path.read_bytes()
        if len(_HMAC) >= 32:
            return _HMAC
    key = secrets.token_bytes(32)
    _atomic_secret_file(path, key)
    _HMAC = key
    return _HMAC


def token_hash(token: str) -> str:
    return hmac.new(_hmac_key(), token.encode("utf-8"), hashlib.sha256).hexdigest()


def _key_path() -> Path:
    return Path(settings.data_dir) / "auth-rsa.pem"


def _load_or_create_rsa() -> rsa.RSAPrivateKey:
    global _PRIV
    if _PRIV is not None:
        return _PRIV
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        data = path.read_bytes()
        key = serialization.load_pem_private_key(data, password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise TypeError("auth-rsa.pem is not an RSA key")
        _PRIV = key
        return _PRIV
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _atomic_secret_file(path, pem)
    _PRIV = key
    return _PRIV


def ensure_auth_keys() -> None:
    _load_or_create_rsa()
    _hmac_key()


def public_pem() -> str:
    pub = _load_or_create_rsa().public_key()
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def _oaep() -> padding.OAEP:
    return padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )


def _parse_password_blob(obj: object) -> dict:
    if not isinstance(obj, dict):
        raise ValueError("bad blob")
    password = obj.get("p")
    nonce = obj.get("n")
    challenge = obj.get("c")
    ts = obj.get("t")
    if not isinstance(password, str) or not password or len(password) > BLOB_MAX_PASSWORD:
        raise ValueError("bad blob")
    if not isinstance(nonce, str) or not (8 <= len(nonce) <= 32):
        raise ValueError("bad blob")
    if not isinstance(challenge, str) or not challenge:
        raise ValueError("bad blob")
    try:
        when = float(ts)
    except (TypeError, ValueError):
        raise ValueError("bad blob") from None
    if not math.isfinite(when):
        raise ValueError("bad blob")
    if abs(time.time() - when) > BLOB_TTL_SEC:
        raise ValueError("stale blob")
    return {"p": password, "n": nonce, "c": challenge, "t": when}


def encrypt_password_blob(password: str, challenge_id: str, *, nonce: str | None = None, ts: float | None = None) -> str:
    """测试与自检用：与浏览器 Web Crypto RSA-OAEP-SHA256 同一填充。"""
    import base64

    payload = {
        "p": password,
        "n": nonce or secrets.token_hex(8),
        "c": challenge_id,
        "t": int(ts if ts is not None else time.time()),
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    pub = _load_or_create_rsa().public_key()
    cipher = pub.encrypt(raw, _oaep())
    return base64.b64encode(cipher).decode("ascii")


def decrypt_password_blob(cipher_b64: str) -> dict:
    import base64

    raw = base64.b64decode(cipher_b64)
    priv = _load_or_create_rsa()
    plain = priv.decrypt(raw, _oaep())
    obj = json.loads(plain.decode("utf-8"))
    return _parse_password_blob(obj)
