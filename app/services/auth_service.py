from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserInfo


async def login(db: AsyncSession, data: LoginRequest) -> TokenResponse:
    result = await db.execute(select(User).where(User.loginid == data.user_id))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(data.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    access_token = create_access_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        user=UserInfo(id=user.id, loginid=user.loginid, email=user.email, user_ename=user.user_ename, user_role=user.user_role),
    )
