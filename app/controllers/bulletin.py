import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.bulletin import PostOut
from app.schemas.common import PaginatedResponse
from app.services import bulletin_service

# 읽기 전용: 게시글 생성/수정/삭제는 LMS가 DB에 직접 수행한다. 이 API는 조회만 제공.
router = APIRouter(tags=["Bulletin"])


@router.get("", response_model=PaginatedResponse[PostOut])
async def list_posts(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    posts, total = await bulletin_service.list_posts(db, page, size)
    return PaginatedResponse(
        items=[PostOut.model_validate(p) for p in posts],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) or 1,
    )


@router.get("/{post_id}", response_model=PostOut)
async def get_post(post_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await bulletin_service.get_post(db, post_id)
    return PostOut.model_validate(post)
