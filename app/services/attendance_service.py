from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.user import User
from app.schemas.attendance import ManualScanRequest, QRStatusResponse, ScanRequest
from app.services._common import today_start_utc


async def _get_today_record(db: AsyncSession, wid: int) -> AttendanceRecord | None:
    """오늘(ET 기준) 출퇴근 행 조회 — 중복 행이 있어도 최신 1건으로 안전하게 처리"""
    result = await db.execute(
        select(AttendanceRecord)
        .where(
            and_(
                AttendanceRecord.wid == wid,
                AttendanceRecord.checkin >= today_start_utc(),
            )
        )
        .order_by(AttendanceRecord.checkin.desc())
        .limit(1)
    )
    return result.scalars().first()


def _record_check(
    db: AsyncSession,
    record: AttendanceRecord | None,
    wid: int,
    ip: str | None,
    device: str | None,
    now: datetime,
) -> AttendanceRecord:
    """오늘 기록 유무에 따라 체크인/체크아웃 결정 (없음→체크인, 체크인만→체크아웃, 둘 다→409)"""
    if record is None:
        record = AttendanceRecord(
            wid=wid,
            checkin=now,
            checkinip=ip,
            checkinbrowser=device,
        )
        db.add(record)
    elif record.checkout is None:
        record.checkout = now
        record.checkoutip = ip
        record.checkoutbrowser = device
    else:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already checked in and out today")
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

    now = datetime.now(timezone.utc)
    record = await _get_today_record(db, wid)
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
    record = await _get_today_record(db, data.wid)
    record = _record_check(db, record, data.wid, data.ip, data.device, now)
    await db.flush()
    return record


async def get_today(db: AsyncSession, wid: int) -> AttendanceRecord | None:
    return await _get_today_record(db, wid)


async def get_qr_status(db: AsyncSession, wid: int) -> QRStatusResponse:
    """인증된 직원의 오늘 출퇴근 상태 반환"""
    record = await _get_today_record(db, wid)
    if record is None:
        return QRStatusResponse(status="pending")
    if record.checkout is None:
        return QRStatusResponse(status="checked_in")
    return QRStatusResponse(status="checked_out")


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
