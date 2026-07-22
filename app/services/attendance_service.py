from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ, DAYOFF_EVENT_TYPES
from app.models.attendance import AttendanceRecord
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.attendance import (
    AttendanceCalendarResponse,
    AttendanceDay,
    AttendancePair,
    CalendarSummary,
    DayInfo,
    ManualScanRequest,
    ScanRequest,
)
from app.services import holiday_service, schedule_service
from app.services._common import today_start_utc


async def _get_latest_today_record(db: AsyncSession, wid: int) -> AttendanceRecord | None:
    """오늘(ET 기준) 가장 최근 출퇴근 행 조회"""
    result = await db.execute(
        select(AttendanceRecord)
        .where(
            and_(
                AttendanceRecord.wid == wid,
                AttendanceRecord.checkin >= today_start_utc(),
            )
        )
        # checkin이 같은 초로 저장돼도(DATETIME 초 단위) 최신 행이 결정적이도록 id 보조 정렬
        .order_by(AttendanceRecord.checkin.desc(), AttendanceRecord.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _get_today_records(db: AsyncSession, wid: int) -> list[AttendanceRecord]:
    """오늘(ET 기준) 전체 출퇴근 행 — checkin 오름차순 (하루 여러 in/out 쌍 허용)"""
    result = await db.execute(
        select(AttendanceRecord)
        .where(
            and_(
                AttendanceRecord.wid == wid,
                AttendanceRecord.checkin >= today_start_utc(),
            )
        )
        .order_by(AttendanceRecord.checkin.asc(), AttendanceRecord.id.asc())
    )
    return list(result.scalars().all())


def _record_check(
    db: AsyncSession,
    record: AttendanceRecord | None,
    wid: int,
    ip: str | None,
    device: str | None,
    now: datetime,
) -> AttendanceRecord:
    """최근 행 상태에 따라 체크인/체크아웃 결정 — 하루 여러 in/out 쌍 허용 (LMS와 동일).

    미완료(checkout 없는) 행이 있으면 그 행에 체크아웃, 아니면 새 행에 체크인.
    """
    if record is not None and record.checkout is None:
        record.checkout = now
        record.checkoutip = ip
        record.checkoutbrowser = device
    else:
        record = AttendanceRecord(
            wid=wid,
            checkin=now,
            checkinip=ip,
            checkinbrowser=device,
        )
        db.add(record)
    return record


async def process_scan(db: AsyncSession, data: ScanRequest) -> AttendanceRecord:
    """스캐너가 QR 읽고 호출 — e{user_id} 형식 파싱 후 출퇴근 기록"""
    token = data.token.strip()
    if not token.startswith("e"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR format")
    try:
        wid = int(token[1:])
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR format")

    # 존재하지 않거나 퇴사(soft-delete)한 id로 정크 출퇴근 행이 삽입되지 않도록 검증
    # (manual 경로와 동일한 활성 사용자 확인 — 무인증 엔드포인트라 최소한의 무결성 방어)
    result = await db.execute(select(User).where(User.id == wid))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")

    now = datetime.now(timezone.utc)
    record = await _get_latest_today_record(db, wid)
    record = _record_check(db, record, wid, data.ip, data.device, now)
    await db.flush()
    return record


async def process_manual(db: AsyncSession, data: ManualScanRequest) -> AttendanceRecord:
    """키오스크 이름 검색 → 직원 선택 시 호출 — wid로 바로 출퇴근 기록"""
    result = await db.execute(select(User).where(User.id == data.wid))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")

    now = datetime.now(timezone.utc)
    record = await _get_latest_today_record(db, data.wid)
    record = _record_check(db, record, data.wid, data.ip, data.device, now)
    await db.flush()
    return record


async def get_today_records(db: AsyncSession, wid: int) -> list[AttendanceRecord]:
    return await _get_today_records(db, wid)


def _et_date(dt: datetime) -> date:
    """naive UTC(DB 저장값) → ET 날짜"""
    return dt.replace(tzinfo=timezone.utc).astimezone(APP_TZ).date()


async def _dayoffs_by_date(
    db: AsyncSession, user: User, from_date: date, to_date: date
) -> dict[date, Schedule]:
    """본인 스케줄 중 '근무 아님' 유형을 날짜별로 펼침 (스팬 휴가는 각 날짜에 매핑)"""
    schedules = await schedule_service.get_schedule(db, user, from_date, to_date)
    by_date: dict[date, Schedule] = {}
    for s in schedules:
        if (s.eventtype or "").strip().lower() not in DAYOFF_EVENT_TYPES:
            continue
        d = max(s.sdate, from_date)
        end = min(s.edate or s.sdate, to_date)
        while d <= end:
            by_date.setdefault(d, s)
            d += timedelta(days=1)
    return by_date


def _day_off_fields(s: Schedule | None) -> dict:
    if s is None:
        return dict(day_off=False, day_off_all_day=None, day_off_stime=None, day_off_etime=None, day_off_name=None)
    return dict(
        day_off=True,
        # allday='Y' 또는 시간 미지정이면 종일 휴가, 아니면 부분 휴가
        day_off_all_day=s.allday == "Y" or (not s.stime and not s.etime),
        day_off_stime=s.stime,
        day_off_etime=s.etime,
        day_off_name=s.eventname or None,
    )


async def get_day_info(db: AsyncSession, user: User) -> DayInfo:
    """오늘(ET)의 휴일/휴가 여부 — 홈 화면 안내용"""
    today = datetime.now(APP_TZ).date()
    holidays = await holiday_service.get_holidays(db, user.bid, today, today)
    dayoff = (await _dayoffs_by_date(db, user, today, today)).get(today)
    fields = _day_off_fields(dayoff)
    return DayInfo(
        is_holiday=bool(holidays),
        holiday_name=holidays[0].holidaynm if holidays else None,
        is_day_off=fields["day_off"],
        day_off_all_day=fields["day_off_all_day"],
        day_off_stime=fields["day_off_stime"],
        day_off_etime=fields["day_off_etime"],
        day_off_name=fields["day_off_name"],
    )


async def get_calendar(db: AsyncSession, user: User, year: int, month: int) -> AttendanceCalendarResponse:
    """월 캘린더 — 일자별 출근/휴일/휴가 상태 병합"""
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    # 월 경계는 ET 자정 기준 → UTC로 변환해 checkin 범위 조회
    start_utc = datetime(year, month, 1, tzinfo=APP_TZ).astimezone(timezone.utc)
    next_first = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    end_utc = datetime(next_first.year, next_first.month, 1, tzinfo=APP_TZ).astimezone(timezone.utc)

    result = await db.execute(
        select(AttendanceRecord)
        .where(
            AttendanceRecord.wid == user.id,
            AttendanceRecord.checkin >= start_utc,
            AttendanceRecord.checkin < end_utc,
        )
        .order_by(AttendanceRecord.checkin.asc(), AttendanceRecord.id.asc())
    )
    records_by_day: dict[date, list[AttendanceRecord]] = {}
    for r in result.scalars():
        records_by_day.setdefault(_et_date(r.checkin), []).append(r)  # 하루 여러 in/out 쌍

    holidays_by_day = {
        h.sdate: h.holidaynm for h in await holiday_service.get_holidays(db, user.bid, first, last)
    }
    dayoffs_by_day = await _dayoffs_by_date(db, user, first, last)

    days: list[AttendanceDay] = []
    d = first
    while d <= last:
        recs = records_by_day.get(d)
        holiday = d in holidays_by_day
        dayoff = dayoffs_by_day.get(d)
        if recs:
            day_status = "worked"          # 휴일/휴가와 겹치면 아래 필드로 병기 ("휴일 근무")
        elif holiday:
            day_status = "holiday"
        elif dayoff is not None:
            day_status = "dayoff"
        else:
            day_status = "none"
        days.append(AttendanceDay(
            date=d,
            status=day_status,
            checkin=recs[0].checkin if recs else None,      # 첫 출근 (구버전 호환)
            checkout=recs[-1].checkout if recs else None,   # 마지막 행 퇴근 (미완료면 null)
            records=[AttendancePair.model_validate(r) for r in (recs or [])],
            holiday_name=holidays_by_day.get(d),
            **_day_off_fields(dayoff),
        ))
        d += timedelta(days=1)

    return AttendanceCalendarResponse(
        year=year,
        month=month,
        days=days,
        summary=CalendarSummary(
            worked_days=len(records_by_day),
            holiday_days=len(holidays_by_day),
            dayoff_days=len(dayoffs_by_day),
        ),
    )


async def get_history(
    db: AsyncSession,
    wid: int,
    from_date: datetime,
    to_date: datetime,
    page: int,
    size: int,
) -> tuple[list[AttendanceRecord], int]:
    base_query = select(AttendanceRecord).where(
        AttendanceRecord.wid == wid,
        AttendanceRecord.checkin >= from_date,
        AttendanceRecord.checkin <= to_date,
    )
    total = (await db.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
    result = await db.execute(
        base_query.order_by(AttendanceRecord.checkin.desc()).offset((page - 1) * size).limit(size)
    )
    return result.scalars().all(), total
