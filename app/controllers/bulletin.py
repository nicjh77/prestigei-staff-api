import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.bulletin import PostCreate, PostOut, PostUpdate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services import bulletin_service

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


@router.post("", response_model=PostOut)
async def create_post(data: PostCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await bulletin_service.create_post(db, current_user, data)
    return PostOut.model_validate(post)


@router.put("/{post_id}", response_model=MessageResponse)
async def update_post(post_id: int, data: PostUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await bulletin_service.update_post(db, post_id, current_user, data)
    return MessageResponse(message="Post updated")


@router.delete("/{post_id}", response_model=MessageResponse)
async def delete_post(post_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await bulletin_service.delete_post(db, post_id, current_user)
    return MessageResponse(message="Post deleted")
