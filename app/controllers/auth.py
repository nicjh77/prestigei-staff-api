from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import (
    LOGIN_LIMIT,
    LOGIN_WINDOW,
    REFRESH_LIMIT,
    REFRESH_WINDOW,
    rate_limit,
)
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.common import MessageResponse
from app.services import auth_service

router = APIRouter(tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(LOGIN_LIMIT, LOGIN_WINDOW, "login"))],
)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, data)


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    dependencies=[Depends(rate_limit(REFRESH_LIMIT, REFRESH_WINDOW, "refresh"))],
)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.refresh_access_token(db, data.refresh_token, data.device_id)


@router.post("/logout", response_model=MessageResponse)
async def logout(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, data.refresh_token)
    return MessageResponse(message="Logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await auth_service.logout_all(db, current_user.id)
    return MessageResponse(message="All sessions logged out")
