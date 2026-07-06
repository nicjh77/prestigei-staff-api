from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.announcement import Announcement, AnnouncementRead
from app.models.user import User

# 읽기 전용: 공지 생성/수정/삭제는 LMS가 DB에 직접 수행한다. 이 서비스는 조회만 제공.
_VISIBLE_ROLES: dict[str, list[str]] = {
    "staff":   ["all", "staff"],
    "manager": ["all", "staff", "manager"],
    "admin":   ["all", "staff", "manager"],
}


def _active_filter(query, user_role: str):
    now = datetime.now(timezone.utc)
    visible = _VISIBLE_ROLES.get(user_role, ["all"])
    return query.where(
        Announcement.deleted_at.is_(None),
        (Announcement.publish_at.is_(None)) | (Announcement.publish_at <= now),
        (Announcement.expire_at.is_(None)) | (Announcement.expire_at >= now),
        Announcement.target_role.in_(visible),
    )


async def list_announcements(db: AsyncSession, user: User, unread_only: bool, page: int, size: int):
    base = _active_filter(select(Announcement), user.user_role)
    if unread_only:
        read_ids = select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id)
        base = base.where(Announcement.id.not_in(read_ids))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    result = await db.execute(
        base.order_by(Announcement.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    items = result.scalars().all()

    read_result = await db.execute(
        select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id)
    )
    read_ids_set = set(read_result.scalars().all())
    return items, total, read_ids_set


async def get_announcement(db: AsyncSession, announcement_id: int, user: User) -> Announcement:
    # 목록과 동일한 가시성 필터 적용 — 역할/게시/만료 조건을 우회한 id 직접 조회(IDOR) 차단
    stmt = _active_filter(select(Announcement), user.user_role).where(Announcement.id == announcement_id)
    result = await db.execute(stmt)
    ann = result.scalar_one_or_none()
    if ann is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")

    # Mark as read (upsert)
    read_result = await db.execute(
        select(AnnouncementRead).where(
            AnnouncementRead.announcement_id == announcement_id,
            AnnouncementRead.user_id == user.id,
        )
    )
    if read_result.scalar_one_or_none() is None:
        db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user.id, read_at=datetime.now(timezone.utc)))

    return ann


async def get_unread_count(db: AsyncSession, user: User) -> int:
    base = _active_filter(select(Announcement), user.user_role)
    read_ids = select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id)
    base = base.where(Announcement.id.not_in(read_ids))
    result = await db.execute(select(func.count()).select_from(base.subquery()))
    return result.scalar_one()
