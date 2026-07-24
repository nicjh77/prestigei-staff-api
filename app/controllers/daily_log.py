from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.daily_log import DailyLogOut, TaskReportOut
from app.services import daily_log_service

router = APIRouter(tags=["Daily Log"])


def _today_et() -> date:
    # "오늘"은 앱 전역과 동일하게 Eastern Time(APP_TZ) 기준 — 서버 로컬 TZ에 의존하지 않음
    return datetime.now(APP_TZ).date()


def _default_from_date() -> date:
    return _today_et() - timedelta(days=7)  # 오늘 기준 일주일 전


def _default_to_date() -> date:
    return _today_et()  # 오늘까지 — 미래(내일) logdate는 기본 조회에서 제외


@router.get("", response_model=list[DailyLogOut])
async def get_daily_logs(
    from_date: date = Query(default_factory=_default_from_date),
    to_date: date = Query(default_factory=_default_to_date),
    status: list[str] | None = Query(default=None, description="태스크 status 필터 (반복 지정 가능). 생략 시 전체"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logs = await daily_log_service.get_daily_logs(db, current_user.id, from_date, to_date, status)
    return logs


@router.get("/tasks", response_model=list[TaskReportOut])
async def get_task_report(
    from_date: date = Query(default_factory=_default_from_date),
    to_date: date = Query(default_factory=_default_to_date),
    status: list[str] | None = Query(default=None, description="태스크 status 필터 (반복 지정 가능). 생략 시 전체"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """태스크 리포트 — 기간 내 내 로그(logdate)가 있는 태스크 + 그 로그 중첩 (LMS Task Report와 동일)"""
    return await daily_log_service.get_task_report(db, current_user.id, from_date, to_date, status)
