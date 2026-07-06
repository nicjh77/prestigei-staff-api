import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_manager
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate, UnreadCountOut
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services import announcement_service

router = APIRouter(tags=["Announcements"])


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = await announcement_service.get_unread_count(db, current_user)
    return UnreadCountOut(count=count)


@router.get("", response_model=PaginatedResponse[AnnouncementOut])
async def list_announcements(
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total, read_ids = await announcement_service.list_announcements(db, current_user, unread_only, page, size)
    out = [
        AnnouncementOut(
            id=a.id, title=a.title, content=a.content, target_role=a.target_role,
            priority=a.priority, publish_at=a.publish_at, expire_at=a.expire_at,
            is_read=a.id in read_ids, created_at=a.created_at,
        )
        for a in items
    ]
    return PaginatedResponse(items=out, total=total, page=page, size=size, pages=math.ceil(total / size) or 1)


@router.get("/{announcement_id}", response_model=AnnouncementOut)
async def get_announcement(announcement_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ann = await announcement_service.get_announcement(db, announcement_id, current_user)
    return AnnouncementOut(
        id=ann.id, title=ann.title, content=ann.content, target_role=ann.target_role,
        priority=ann.priority, publish_at=ann.publish_at, expire_at=ann.expire_at,
        is_read=True, created_at=ann.created_at,
    )


@router.post("", response_model=AnnouncementOut)
async def create_announcement(data: AnnouncementCreate, current_user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    ann = await announcement_service.create_announcement(db, current_user, data)
    return AnnouncementOut(
        id=ann.id, title=ann.title, content=ann.content, target_role=ann.target_role,
        priority=ann.priority, publish_at=ann.publish_at, expire_at=ann.expire_at,
        is_read=False, created_at=ann.created_at,
    )


@router.put("/{announcement_id}", response_model=MessageResponse)
async def update_announcement(announcement_id: int, data: AnnouncementUpdate, current_user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    await announcement_service.update_announcement(db, announcement_id, data)
    return MessageResponse(message="Announcement updated")


@router.delete("/{announcement_id}", response_model=MessageResponse)
async def delete_announcement(announcement_id: int, current_user: User = Depends(require_manager), db: AsyncSession = Depends(get_db)):
    await announcement_service.delete_announcement(db, announcement_id)
    return MessageResponse(message="Announcement deleted")
