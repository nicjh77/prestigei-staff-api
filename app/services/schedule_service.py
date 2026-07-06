from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import Schedule


async def get_schedule(db: AsyncSession, tid: int, from_date: date, to_date: date) -> list[Schedule]:
    result = await db.execute(
        select(Schedule).where(
            Schedule.tid == tid,
            Schedule.sdate >= from_date,
            Schedule.sdate <= to_date,
        ).order_by(Schedule.sdate)
    )
    return result.scalars().all()
