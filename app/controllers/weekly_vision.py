from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.weekly_vision import WeeklyVisionListOut, WeeklyVisionOut
from app.services import weekly_vision_service

router = APIRouter(tags=["Weekly Vision"])


@router.get("", response_model=list[WeeklyVisionListOut])
async def list_visions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    visions = await weekly_vision_service.list_visions(db)
    return [WeeklyVisionListOut.model_validate(v) for v in visions]


@router.get("/latest", response_model=WeeklyVisionOut)
async def get_latest_vision(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vision = await weekly_vision_service.get_latest_vision(db)
    return WeeklyVisionOut.model_validate(vision)


@router.get("/{vision_id}", response_model=WeeklyVisionOut)
async def get_vision(
    vision_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vision = await weekly_vision_service.get_vision(db, vision_id)
    return WeeklyVisionOut.model_validate(vision)
