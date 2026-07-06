from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.schedule import ScheduleOut
from app.services import schedule_service

# 읽기 전용: 스케줄 생성/수정/삭제는 LMS가 DB에 직접 수행한다. 이 API는 조회만 제공.
router = APIRouter(tags=["Schedule"])


def _week_start() -> date:
    # "오늘"은 앱 전역과 동일하게 Eastern Time(APP_TZ) 기준 — 서버 로컬 TZ에 의존하지 않음
    today = datetime.now(APP_TZ).date()
    return today - timedelta(days=today.weekday())  # 그 주 월요일


def _week_end() -> date:
    return _week_start() + timedelta(days=6)  # 그 주 일요일


@router.get("", response_model=list[ScheduleOut])
async def get_schedule(
    from_date: date = Query(default_factory=_week_start),
    to_date: date = Query(default_factory=_week_end),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedules = await schedule_service.get_schedule(db, current_user.tid, from_date, to_date)
    return [ScheduleOut.model_validate(s) for s in schedules]
