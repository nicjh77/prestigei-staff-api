from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bulletin import BulletinPost


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
