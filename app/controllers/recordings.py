from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.recording import BranchOut, RecordingSessionOut
from app.services import recording_session_service

# 앱 Recording 화면 보조 API (읽기 전용). 녹음 파일 업로드/변환은 아직 없다 (2026-09-25 오너 결정 — 앱이 폰에 보관, 버튼만).
router = APIRouter(tags=["Recordings"])


def _today() -> date:
    return datetime.now(APP_TZ).date()


@router.get("/branches", response_model=list[BranchOut])
async def branches(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """일정 선택 시트의 지점 목록 (전 지점)."""
    return await recording_session_service.list_branches(db)


@router.get("/sessions", response_model=list[RecordingSessionOut])
async def sessions(
    type: str = Query(..., pattern="^(tutoring|class)$"),
    date_: date | None = Query(None, alias="date", description="기본 오늘(ET)"),
    bid: int | None = Query(None, description="지점. 생략 = 내 지점, 0 = 전체"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tutoring(t_tutorschedule) / Class(t_classdate) 일정 목록 — 녹음을 어느 일정에 붙일지 고르는 용도.
    LMS recording 사이트의 목록과 같은 SQL. 로그인 사용자가 담당 교사인 일정(mine)이 앞에 온다."""
    d = date_ or _today()
    if bid is None:
        bid_filter = current_user.bid
    elif bid == 0:
        bid_filter = None
    else:
        bid_filter = bid
    return await recording_session_service.list_sessions(db, current_user, type, d, bid_filter)
