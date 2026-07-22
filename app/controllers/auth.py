from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import LOGIN_LIMIT, LOGIN_WINDOW, rate_limit
from app.schemas.auth import LoginRequest, TokenResponse
from app.services import auth_service

router = APIRouter(tags=["Auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(LOGIN_LIMIT, LOGIN_WINDOW, "login"))],
)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, data)
