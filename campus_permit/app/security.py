"""密碼雜湊、Token、加密等安全工具。"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet

from . import config

_ph = PasswordHasher()  # 預設就是 Argon2id
_fernet = Fernet(config.DATA_ENCRYPTION_KEY.encode())


def utcnow() -> datetime:
    """全專案統一使用「不帶時區的 UTC 時間」，避免 SQLite 比較時間出錯。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


# ---------- 密碼 ----------
def hash_password(password: str) -> str:
    return _ph.hash(password)


# 帳號不存在時也拿這個假雜湊做一次驗證，讓回應時間一致（防時序攻擊／帳號列舉）
DUMMY_HASH = _ph.hash("dummy-password-for-timing-only")


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# ---------- 個資加密（Fernet = AES + HMAC） ----------
def encrypt_text(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def decrypt_text(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()


# ---------- Refresh Token：隨機字串，資料庫只存雜湊 ----------
def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- Access Token（JWT） ----------
def create_access_token(user_id: int, session_id: int) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "iat": _ts(now),
        "exp": _ts(now + timedelta(minutes=config.ACCESS_TOKEN_MINUTES)),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=["HS256"],  # 固定演算法，防止 alg=none 攻擊
            options={"require": ["exp", "sub", "sid"]},
        )
    except jwt.PyJWTError:
        return None
