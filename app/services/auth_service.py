import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.models.user import RefreshToken, User
from app.schemas.auth import AccessTokenResponse, LoginRequest, TokenResponse, UserInfo


async def login(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    result = await db.execute(select(User).where(User.loginid == data.user_id))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(data.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    access_token = create_access_token({"sub": str(user.id)})
    raw_refresh, token_hash = create_refresh_token()

    db.add(RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        device_id=data.device_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        created_at=datetime.now(timezone.utc),
    ))
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user=UserInfo(id=user.id, loginid=user.loginid, email=user.email, user_ename=user.user_ename, user_role=user.user_role),
    )


async def refresh_access_token(db: AsyncSession, raw_token: str, device_id: str | None) -> AccessTokenResponse:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    db_token = result.scalar_one_or_none()
    if db_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # 기존 토큰 무효화
    db_token.revoked_at = datetime.now(timezone.utc)

    # 새 토큰 발급 (슬라이딩)
    access_token = create_access_token({"sub": str(db_token.user_id)})
    raw_refresh, new_hash = create_refresh_token()
    db.add(RefreshToken(
        user_id=db_token.user_id,
        token_hash=new_hash,
        device_id=device_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        created_at=datetime.now(timezone.utc),
    ))
    await db.flush()

    return AccessTokenResponse(access_token=access_token, refresh_token=raw_refresh)


async def logout(db: AsyncSession, raw_token: str) -> None:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    db_token = result.scalar_one_or_none()
    if db_token:
        db_token.revoked_at = datetime.now(timezone.utc)


async def logout_all(db: AsyncSession, user_id: int) -> None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    tokens = result.scalars().all()
    now = datetime.now(timezone.utc)
    for token in tokens:
        token.revoked_at = now
