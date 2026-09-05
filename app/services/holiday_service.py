from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datelist import DateList
from app.models.holiday import BranchHoliday


@dataclass(frozen=True)
class Holiday:
    sdate: date
    holidaynm: str | None


async def get_holidays(db: AsyncSession, bid: int | None, from_date: date, to_date: date) -> list[Holiday]:
    """기간 내 휴일 — 두 소스를 날짜별로 병합 (2026-09-05 오너 확인).

    1) t_datelist: 기본 달력(요일) + 공휴일(holidayyn='Y', 예: Independence Day) — 전 지점 공통.
       (t_datelist.bid 컬럼은 2026-07에 추가됐지만 LMS가 쓰지 않아 전부 NULL — 필터에 사용하지 않음.)
    2) t_holiday: 지점별 행사/지역 휴일(LMS Staff Schedule > Manage Holidays, bid int). 로그인 사용자 지점만.
    같은 날짜에 둘 다 있으면 공휴일 이름 우선.
    """
    result = await db.execute(
        select(DateList).where(
            DateList.holidayyn == "Y",
            DateList.sdate >= from_date,
            DateList.sdate <= to_date,
        )
    )
    by_date: dict[date, Holiday] = {h.sdate: Holiday(h.sdate, h.holidaynm) for h in result.scalars()}

    if bid is not None:
        result = await db.execute(
            select(BranchHoliday).where(
                BranchHoliday.holidayyn == "Y",
                BranchHoliday.bid == bid,
                BranchHoliday.sdate >= from_date,
                BranchHoliday.sdate <= to_date,
            )
        )
        for h in result.scalars():
            by_date.setdefault(h.sdate, Holiday(h.sdate, h.holidaynm))

    return [by_date[d] for d in sorted(by_date)]
