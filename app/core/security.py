import hashlib
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    """MySQL PASSWORD() compatible hash: *uppercase(SHA1(SHA1(plain)))"""
    first = hashlib.sha1(plain.encode()).digest()
    second = hashlib.sha1(first).hexdigest().upper()
    return f"*{second}"


def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload
