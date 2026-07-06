from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services._common import apply_updates


async def get_schedule(db: AsyncSession, tid: int, from_date: date, to_date: date) -> list[Schedule]:
    result = await db.execute(
        select(Schedule).where(
            Schedule.tid == tid,
            Schedule.sdate >= from_date,
            Schedule.sdate <= to_date,
        ).order_by(Schedule.sdate)
    )
    return result.scalars().all()


async def create_schedule(db: AsyncSession, data: ScheduleCreate, wid: int) -> Schedule:
    now = datetime.now(timezone.utc)
    schedule = Schedule(**data.model_dump(), ins_date=now, upd_date=now, wid=wid)
    db.add(schedule)
    await db.flush()
    return schedule


async def update_schedule(db: AsyncSession, schedule_id: int, data: ScheduleUpdate, wid: int) -> Schedule:
    result = await db.execute(select(Schedule).where(Schedule.schid == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    apply_updates(schedule, data)
    schedule.upd_date = datetime.now(timezone.utc)
    schedule.wid = wid
    return schedule


async def delete_schedule(db: AsyncSession, schedule_id: int) -> None:
    result = await db.execute(select(Schedule).where(Schedule.schid == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    await db.delete(schedule)
