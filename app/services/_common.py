from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ


def today_start_et() -> datetime:
    """오늘 ET 자정 (naive 벽시계).

    t_usertimecheck는 LMS/터미널이 **ET 현지 시각을 naive로** 저장하는 테이블이다
    (프로덕션 데이터로 확인: 아침 출근이 08:0x로 저장됨 — UTC였다면 새벽 4시가 됨).
    따라서 조회 경계도 ET naive로 맞춰야 한다. UTC 변환 금지.
    """
    return datetime.now(APP_TZ).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


async def get_or_404(db: AsyncSession, stmt, detail: str):
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return obj


def apply_updates(obj, data) -> None:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
