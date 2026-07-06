from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bulletin import BulletinPost
from app.models.user import User
from app.schemas.bulletin import PostCreate, PostUpdate
from app.services._common import apply_updates


async def list_posts(db: AsyncSession, page: int, size: int) -> tuple[list[BulletinPost], int]:
    base_query = select(BulletinPost).where(BulletinPost.delyn == "N")
    total = (await db.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
    result = await db.execute(
        base_query.order_by(BulletinPost.regdate.desc()).offset((page - 1) * size).limit(size)
    )
    return result.scalars().all(), total


async def get_post(db: AsyncSession, post_id: int) -> BulletinPost:
    result = await db.execute(
        select(BulletinPost).where(BulletinPost.id == post_id, BulletinPost.delyn == "N")
    )
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


async def create_post(db: AsyncSession, user: User, data: PostCreate) -> BulletinPost:
    post = BulletinPost(
        wid=user.wid,
        title=data.title,
        details=data.details,
        bid=data.bid,
        regdate=date.today(),
    )
    db.add(post)
    await db.flush()
    return post


async def update_post(db: AsyncSession, post_id: int, user: User, data: PostUpdate) -> BulletinPost:
    result = await db.execute(select(BulletinPost).where(BulletinPost.id == post_id, BulletinPost.delyn == "N"))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.wid != user.wid and user.user_role not in ("manager", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    apply_updates(post, data)
    post.updwid = user.wid
    post.upddate = datetime.now(timezone.utc)
    return post


async def delete_post(db: AsyncSession, post_id: int, user: User) -> None:
    result = await db.execute(select(BulletinPost).where(BulletinPost.id == post_id, BulletinPost.delyn == "N"))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.wid != user.wid and user.user_role not in ("manager", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    post.delyn = "Y"
    post.updwid = user.wid
    post.upddate = datetime.now(timezone.utc)
