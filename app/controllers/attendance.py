import math
from datetime import datetime, timedelta

from app.core.constants import APP_TZ

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import SCAN_LIMIT, SCAN_WINDOW, rate_limit
from app.models.user import User
from app.schemas.attendance import (
    AttendanceCalendarResponse,
    AttendanceRecordOut,
    ManualScanRequest,
    QRStatusResponse,
    ScanRequest,
    TodayAttendance,
)
from app.schemas.common import PaginatedResponse
from app.services import attendance_service

router = APIRouter(tags=["Attendance"])


@router.get("/qr/status", response_model=QRStatusResponse)
async def get_qr_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """앱이 폴링으로 스캔 완료 여부 확인 — 토큰 없이 인증된 직원 ID로 조회"""
    return await attendance_service.get_qr_status(db, current_user.id)


@router.post(
    "/scan",
    response_model=AttendanceRecordOut,
    dependencies=[Depends(rate_limit(SCAN_LIMIT, SCAN_WINDOW, "scan"))],
)
async def scan(
    data: ScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """스캐너가 QR 읽고 호출 — 토큰 검증 후 출퇴근 기록"""
    record = await attendance_service.process_scan(db, data)
    return AttendanceRecordOut.model_validate(record)


@router.post(
    "/manual",
    response_model=AttendanceRecordOut,
    dependencies=[Depends(rate_limit(SCAN_LIMIT, SCAN_WINDOW, "scan"))],
)
async def manual_scan(
    data: ManualScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """키오스크 이름 검색 → 직원 선택 시 호출 — 인증 없이 wid로 바로 출퇴근 기록"""
    record = await attendance_service.process_manual(db, data)
    return AttendanceRecordOut.model_validate(record)


@router.get("/today", response_model=TodayAttendance)
async def today(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await attendance_service.get_today(db, current_user.id)
    day_info = await attendance_service.get_day_info(db, current_user)
    return TodayAttendance(
        checkin=record.checkin if record else None,
        checkout=record.checkout if record else None,
        day_info=day_info,
    )


@router.get("/calendar", response_model=AttendanceCalendarResponse)
async def calendar_view(
    year: int | None = Query(default=None, ge=2014, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """월 단위 출퇴근 캘린더 — 일자별 출근/휴일/휴가 상태 + 요약 (기본: 이번 달, ET)"""
    now = datetime.now(APP_TZ)
    return await attendance_service.get_calendar(db, current_user, year or now.year, month or now.month)


@router.get("/history", response_model=PaginatedResponse[AttendanceRecordOut])
async def history(
    from_date: datetime = Query(default_factory=lambda: (datetime.now(APP_TZ).replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)),
    to_date: datetime = Query(default_factory=lambda: datetime.now(APP_TZ)),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    records, total = await attendance_service.get_history(db, current_user.id, from_date, to_date, page, size)
    items = [AttendanceRecordOut.model_validate(r) for r in records]
    return PaginatedResponse(items=items, total=total, page=page, size=size, pages=math.ceil(total / size) or 1)
