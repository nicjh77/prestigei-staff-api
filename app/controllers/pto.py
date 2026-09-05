from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.pto import PtoCreate, PtoCreateResponse, PtoItem, PtoListResponse, PtoUpdate
from app.services import pto_service

# 자가 제출 PTO — 이 API에서 t_schedule에 쓰는 유일한 경로. 본인·PTO 타입·오늘(ET) 이후 행만.
router = APIRouter(tags=["PTO"])


def _current_year() -> int:
    return datetime.now(APP_TZ).year


@router.get("", response_model=PtoListResponse)
async def list_pto(
    year: int = Query(default_factory=_current_year, ge=2014, le=2100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """연도별 내 PTO 목록 + 휴가 잔여(배정/사용/남은 일수)"""
    return await pto_service.list_pto(db, current_user, year)


@router.post("", response_model=PtoCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_pto(
    data: PtoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """여러 날 제출 → 하루 1행씩 생성 (LMS와 동일). 과거 날짜 403, 같은 날 같은 타입 중복 409.
    dayoff는 휴일(공휴일·내 지점)을 자동 제외하고 `skipped`로 알려준다 (전부 휴일이면 400)."""
    return await pto_service.create_pto(db, current_user, data)


@router.patch("/{schid}", response_model=PtoItem)
async def update_pto(
    schid: int,
    data: PtoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await pto_service.update_pto(db, current_user, schid, data)


@router.delete("/{schid}", response_model=MessageResponse)
async def delete_pto(
    schid: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await pto_service.delete_pto(db, current_user, schid)
    return MessageResponse(message="PTO entry deleted")
