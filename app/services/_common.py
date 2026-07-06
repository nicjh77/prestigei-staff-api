from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ


def today_start_utc() -> datetime:
    """ET midnight today → UTC."""
    return datetime.now(APP_TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


async def get_or_404(db: AsyncSession, stmt, detail: str):
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return obj


def apply_updates(obj, data) -> None:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
