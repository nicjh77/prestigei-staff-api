from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_manager
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.schedule import ScheduleCreate, ScheduleOut, ScheduleUpdate
from app.services import schedule_service

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


@router.post("", response_model=ScheduleOut)
async def create_schedule(
    data: ScheduleCreate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    schedule = await schedule_service.create_schedule(db, data, current_user.wid)
    return ScheduleOut.model_validate(schedule)


@router.put("/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    schedule = await schedule_service.update_schedule(db, schedule_id, data, current_user.wid)
    return ScheduleOut.model_validate(schedule)


@router.delete("/{schedule_id}", response_model=MessageResponse)
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    await schedule_service.delete_schedule(db, schedule_id)
    return MessageResponse(message="Schedule deleted")
