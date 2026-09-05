"""PTO(개인 일정: dayoff / personal / other) 자가 제출 — LMS Staff Schedule과 동일한 행을 t_schedule에 쓴다.

이 API의 "콘텐츠 read-only" 규칙의 예외(자가 서비스). 승인 절차 없음(구두 승인 후 본인 입력).
가드는 서버 검증만: 본인 행(tid = t_user.id) + PTO 타입 + 날짜 >= 오늘(ET). 과거는 역할 무관 차단(LMS에서만).
"""
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    APP_TZ, HALF_AM, HALF_PM, PTO_EVENT_TYPES, WORK_END, WORK_HOURS, WORK_START, now_et,
)
from app.models.schedule import Schedule
from app.models.user import User
from app.models.vacation import Vacation
from app.schemas.pto import (
    PtoBalance, PtoCreate, PtoCreateResponse, PtoDay, PtoItem, PtoListResponse, PtoUpdate, SkippedHoliday,
)
from app.services import holiday_service

_WORK_SECONDS = WORK_HOURS * 60 * 60


def _round2(x: float | Decimal) -> float:
    """MySQL ROUND(x, 2)와 동일한 half-up (Python round는 1.625 → 1.62, MySQL은 1.63)"""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _today() -> date:
    return datetime.now(APP_TZ).date()


def _mode_fields(mode: str, stime: str | None, etime: str | None) -> dict:
    """모드 → LMS 저장값 (stime/etime/allday/halfday)"""
    if mode == "allday":
        return dict(stime=WORK_START, etime=WORK_END, allday="Y", halfday="N")
    if mode == "am":
        return dict(stime=HALF_AM[0], etime=HALF_AM[1], allday="N", halfday="A")
    if mode == "pm":
        return dict(stime=HALF_PM[0], etime=HALF_PM[1], allday="N", halfday="P")
    return dict(stime=stime, etime=etime, allday="N", halfday="N")


def _mode_of(s: Schedule) -> str:
    if s.allday == "Y":
        return "allday"
    if s.halfday == "A":
        return "am"
    if s.halfday == "P":
        return "pm"
    return "custom"


def _seconds(t: str | None) -> int | None:
    try:
        h, m = t.split(":")
        return int(h) * 3600 + int(m) * 60
    except (AttributeError, ValueError):
        return None


def used_days(s: Schedule) -> float:
    """LMS usp_selstaffvacation 공식 그대로 (수정 금지 — LMS 화면과 숫자가 같아야 한다).

    allday=Y → 1.0 / 반차(halfday A·P, 구 'Y') → 0.5 / 8시간 이상 → 1.0 / 음수 → 0 /
    그 외 → ROUND(초/8h*100, 2)/100. 점심시간은 차감하지 않는다. 스팬 행도 행당 1회만 계산(SP와 동일).
    """
    if s.allday == "Y":
        return 1.0
    if s.halfday in ("A", "P", "Y"):
        return 0.5
    st, et = _seconds(s.stime), _seconds(s.etime)
    if st is None or et is None:
        return 0.0
    diff = et - st
    if diff >= _WORK_SECONDS:
        return 1.0
    if diff < 0:
        return 0.0
    return _round2(Decimal(diff) / _WORK_SECONDS * 100) / 100


def _to_item(s: Schedule, today: date) -> PtoItem:
    return PtoItem(
        schid=s.schid,
        date=s.sdate,
        eventtype=s.eventtype,
        eventname=s.eventname or "",
        mode=_mode_of(s),
        stime=s.stime,
        etime=s.etime,
        allday=s.allday,
        halfday=s.halfday,
        days=used_days(s),
        editable=s.sdate >= today,
    )


def _year_range(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


async def _year_rows(db: AsyncSession, user: User, year: int) -> list[Schedule]:
    first, last = _year_range(year)
    result = await db.execute(
        select(Schedule).where(
            Schedule.tid == user.id,
            Schedule.eventtype.in_(PTO_EVENT_TYPES),
            Schedule.sdate >= first,
            Schedule.sdate <= last,
        ).order_by(Schedule.sdate, Schedule.schid)
    )
    return list(result.scalars().all())


async def get_balance(db: AsyncSession, user: User, year: int, rows: list[Schedule] | None = None) -> PtoBalance:
    """배정(t_vacation.vacationday, ayear=달력 연도) vs 사용(dayoff 행 합, YEAR(sdate), tid=t_user.id) — LMS 쿼리와 동일"""
    if rows is None:
        rows = await _year_rows(db, user, year)
    used = _round2(sum(Decimal(str(used_days(s))) for s in rows if s.eventtype == "dayoff"))
    result = await db.execute(
        select(Vacation)
        .where(Vacation.userid == user.id, Vacation.ayear == str(year))
        .order_by(Vacation.id.desc())
        .limit(1)
    )
    v = result.scalar_one_or_none()
    # LMS 쿼리와 동일: 배정 행이 없으면 0.0 (IFNULL) — remaining은 음수가 될 수 있음(경고 표시용, 차단 안 함)
    assigned = float(v.vacationday) if v and v.vacationday is not None else 0.0
    return PtoBalance(
        year=year,
        assigned=assigned,
        used=used,
        remaining=_round2(Decimal(str(assigned)) - Decimal(str(used))),
        from_date=v.fromdate if v else None,
        to_date=v.todate if v else None,
    )


async def list_pto(db: AsyncSession, user: User, year: int) -> PtoListResponse:
    rows = await _year_rows(db, user, year)
    today = _today()
    return PtoListResponse(
        year=year,
        balance=await get_balance(db, user, year, rows),
        items=[_to_item(s, today) for s in rows],
    )


async def _get_own(db: AsyncSession, user: User, schid: int) -> Schedule:
    result = await db.execute(
        select(Schedule).where(
            Schedule.schid == schid,
            Schedule.tid == user.id,
            Schedule.eventtype.in_(PTO_EVENT_TYPES),
        )
    )
    s = result.scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PTO entry not found")
    return s


def _require_not_past(d: date, today: date) -> None:
    if d < today:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Past entries can only be changed in the LMS",
        )


async def _reject_duplicates(
    db: AsyncSession, user: User, eventtype: str, dates: list[date], exclude_schid: int | None = None
) -> None:
    """같은 날 같은 타입 중복 거절 (dayoff 이중 집계 방지). 레거시 스팬 행(sdate~edate)도 포함 판정."""
    conds = [
        Schedule.tid == user.id,
        Schedule.eventtype == eventtype,
        Schedule.sdate <= max(dates),
        func.coalesce(Schedule.edate, Schedule.sdate) >= min(dates),
    ]
    if exclude_schid is not None:
        conds.append(Schedule.schid != exclude_schid)
    result = await db.execute(select(Schedule).where(*conds))
    wanted = set(dates)
    clashes: set[date] = set()
    for s in result.scalars():
        d, end = s.sdate, s.edate or s.sdate
        while d <= end:
            if d in wanted:
                clashes.add(d)
            d += timedelta(days=1)
    if clashes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{eventtype} already exists on: " + ", ".join(d.isoformat() for d in sorted(clashes)),
        )


async def _holidays_on(db: AsyncSession, user: User, dates: list[date]) -> dict[date, str | None]:
    """공휴일(t_datelist) + 내 지점 휴일(t_holiday) — dayoff 자동 제외 판정용"""
    if not dates:
        return {}
    hols = await holiday_service.get_holidays(db, user.bid, min(dates), max(dates))
    wanted = set(dates)
    return {h.sdate: h.holidaynm for h in hols if h.sdate in wanted}


async def create_pto(db: AsyncSession, user: User, data: PtoCreate) -> PtoCreateResponse:
    today = _today()
    for d in data.days:
        _require_not_past(d.date, today)

    # dayoff는 휴일(전체·내 지점)을 자동 제외 — LMS Staff Schedule과 동일 규칙 (오너 2026-09-05).
    # 일요일 등 요일은 지점마다 근무 여부가 달라 건드리지 않는다. personal/other는 휴일에도 그대로 추가.
    days = list(data.days)
    skipped: list[SkippedHoliday] = []
    if data.eventtype == "dayoff":
        hol = await _holidays_on(db, user, [d.date for d in days])
        skipped = [SkippedHoliday(date=d.date, name=hol[d.date]) for d in days if d.date in hol]
        days = [d for d in days if d.date not in hol]
        if not days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All selected dates are holidays — Day Off is not needed on a holiday",
            )

    await _reject_duplicates(db, user, data.eventtype, [d.date for d in days])

    now = now_et()
    rows: list[Schedule] = []
    for d in days:  # 하루 1행 (LMS와 동일: sdate = edate)
        rows.append(Schedule(
            tid=user.id, uid=user.id, wid=user.id,
            sdate=d.date, edate=d.date,
            eventname=data.eventname, eventtype=data.eventtype,
            ins_date=now, upd_date=now,
            **_mode_fields(d.mode, d.stime, d.etime),
        ))
    db.add_all(rows)
    await db.flush()  # schid 확보
    return PtoCreateResponse(items=[_to_item(s, today) for s in rows], skipped=skipped)


async def update_pto(db: AsyncSession, user: User, schid: int, data: PtoUpdate) -> PtoItem:
    today = _today()
    s = await _get_own(db, user, schid)
    _require_not_past(s.sdate, today)

    new_date = data.date or s.sdate
    new_type = data.eventtype or s.eventtype
    if data.date is not None:
        _require_not_past(new_date, today)
    if new_type == "dayoff" and (new_date != s.sdate or new_type != s.eventtype):
        hol = await _holidays_on(db, user, [new_date])
        if new_date in hol:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{new_date.isoformat()} is a holiday ({hol[new_date] or 'Holiday'}) — Day Off is not needed",
            )
    if new_date != s.sdate or new_type != s.eventtype:
        await _reject_duplicates(db, user, new_type, [new_date], exclude_schid=s.schid)

    s.sdate = new_date
    s.edate = new_date  # 앱이 수정한 행은 하루 1행으로 정규화 (레거시 스팬 행이어도)
    s.eventtype = new_type
    if data.eventname is not None:
        s.eventname = data.eventname
    if data.mode is not None:
        for k, v in _mode_fields(data.mode, data.stime, data.etime).items():
            setattr(s, k, v)
    s.upd_date = now_et()
    await db.flush()
    return _to_item(s, today)


async def delete_pto(db: AsyncSession, user: User, schid: int) -> None:
    s = await _get_own(db, user, schid)
    _require_not_past(s.sdate, _today())
    await db.delete(s)
