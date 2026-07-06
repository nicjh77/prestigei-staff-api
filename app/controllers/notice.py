import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.notice import NoticeDetail, NoticeListItem
from app.services import notice_service

router = APIRouter(tags=["Notice"])


@router.get("", response_model=PaginatedResponse[NoticeListItem])
async def list_notices(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await notice_service.list_notices(db, current_user, page, size)
    return PaginatedResponse(
        items=items, total=total, page=page, size=size, pages=math.ceil(total / size) or 1
    )


@router.get("/{notice_id}", response_model=NoticeDetail)
async def get_notice(
    notice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await notice_service.get_notice(db, notice_id, current_user)
