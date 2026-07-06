from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.daily_log import DailyLogOut
from app.services import daily_log_service

router = APIRouter(tags=["Daily Log"])


def _default_from_date() -> date:
    # "오늘"은 앱 전역과 동일하게 Eastern Time(APP_TZ) 기준 — 서버 로컬 TZ에 의존하지 않음
    today = datetime.now(APP_TZ).date()
    return today - timedelta(days=today.weekday() + 1)  # 직전 일요일


def _default_to_date() -> date:
    return _default_from_date() + timedelta(days=6)  # 그 주 토요일


@router.get("", response_model=list[DailyLogOut])
async def get_daily_logs(
    from_date: date = Query(default_factory=_default_from_date),
    to_date: date = Query(default_factory=_default_to_date),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logs = await daily_log_service.get_daily_logs(db, current_user.id, from_date, to_date)
    return logs
