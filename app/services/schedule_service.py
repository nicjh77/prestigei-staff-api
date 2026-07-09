from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import Schedule


async def get_schedule(db: AsyncSession, tid: int | None, from_date: date, to_date: date) -> list[Schedule]:
    # tid 없는 직원(t_teacher 미연결)은 스케줄 주체가 될 수 없음 — IS NULL 쿼리 방지
    if tid is None:
        return []
    # 기간 겹침 판정: sdate~edate 범위가 조회 구간과 겹치면 포함 (edate 없으면 단일일)
    result = await db.execute(
        select(Schedule).where(
            Schedule.tid == tid,
            Schedule.sdate <= to_date,
            func.coalesce(Schedule.edate, Schedule.sdate) >= from_date,
        ).order_by(Schedule.sdate)
    )
    return result.scalars().all()
