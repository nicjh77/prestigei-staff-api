from datetime import date, datetime
from calendar import monthrange

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.holiday import HolidayOut
from app.services import holiday_service

# 읽기 전용: 휴일 데이터는 LMS가 t_datelist에 직접 관리. 이 API는 조회만 제공.
router = APIRouter(tags=["Holidays"])


def _month_start() -> date:
    return datetime.now(APP_TZ).date().replace(day=1)


def _month_end() -> date:
    today = datetime.now(APP_TZ).date()
    return today.replace(day=monthrange(today.year, today.month)[1])


@router.get("", response_model=list[HolidayOut])
async def list_holidays(
    from_date: date = Query(default_factory=_month_start),
    to_date: date = Query(default_factory=_month_end),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """기간 내 휴일 목록 — 전 지점 공통 + 내 지점 휴일 (기본: 이번 달)"""
    holidays = await holiday_service.get_holidays(db, current_user.bid, from_date, to_date)
    return [HolidayOut(date=h.sdate, name=h.holidaynm) for h in holidays]
