from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datelist import DateList


async def get_holidays(db: AsyncSession, bid: int | None, from_date: date, to_date: date) -> list[DateList]:
    """기간 내 휴일 조회 — bid NULL(전 지점 공통) + 내 지점이 포함된 휴일.

    t_datelist.bid는 JSON 배열 문자열('["6","7"]'). 따옴표 포함 LIKE 매칭이라
    "2"가 "12"에 오탐하지 않는다. JSON_CONTAINS는 깨진 행 하나에 쿼리 전체가
    실패하므로 쓰지 않는다.
    """
    branch_cond = DateList.bid.is_(None)
    if bid is not None:
        branch_cond = or_(branch_cond, DateList.bid.like(f'%"{bid}"%'))
    result = await db.execute(
        select(DateList).where(
            DateList.holidayyn == "Y",
            DateList.sdate >= from_date,
            DateList.sdate <= to_date,
            branch_cond,
        ).order_by(DateList.sdate)
    )
    return result.scalars().all()
