from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule import Schedule
from app.models.user import User


async def get_schedule(db: AsyncSession, user: User, from_date: date, to_date: date) -> list[Schedule]:
    # 대상 매칭: 티처 일정은 tid(t_teacher.tid), 일반 직원 일정은 uid(t_user.id)
    subject = [Schedule.uid == user.id]
    if user.tid is not None:
        subject.append(Schedule.tid == user.tid)
    # 기간 겹침 판정: sdate~edate 범위가 조회 구간과 겹치면 포함 (edate 없으면 단일일)
    result = await db.execute(
        select(Schedule).where(
            or_(*subject),
            Schedule.sdate <= to_date,
            func.coalesce(Schedule.edate, Schedule.sdate) >= from_date,
        ).order_by(Schedule.sdate)
    )
    return result.scalars().all()
