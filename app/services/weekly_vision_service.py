from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weekly_vision import WeeklyVision


async def list_visions(db: AsyncSession) -> list[WeeklyVision]:
    result = await db.execute(
        select(WeeklyVision).where(WeeklyVision.is_hidden == "N").order_by(WeeklyVision.created_at.desc())
    )
    return result.scalars().all()


async def get_latest_vision(db: AsyncSession) -> WeeklyVision:
    result = await db.execute(
        select(WeeklyVision).where(WeeklyVision.is_hidden == "N").order_by(WeeklyVision.created_at.desc()).limit(1)
    )
    vision = result.scalar_one_or_none()
    if vision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No vision found")
    return vision


async def get_vision(db: AsyncSession, vision_id: int) -> WeeklyVision:
    result = await db.execute(
        select(WeeklyVision).where(WeeklyVision.id == vision_id, WeeklyVision.is_hidden == "N")
    )
    vision = result.scalar_one_or_none()
    if vision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision not found")
    return vision
