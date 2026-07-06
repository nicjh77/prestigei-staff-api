from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,     # 죽은 커넥션 자동 감지 (관리형 MySQL idle timeout 대응)
    pool_recycle=1800,      # 30분마다 커넥션 재생성 — MySQL wait_timeout 초과 방지
    pool_size=10,           # QR 상태 2초 폴링 등 동시 요청 대비 (기본 5 → 10)
    max_overflow=20,        # 순간 스파이크 시 최대 30 커넥션까지
    pool_timeout=10,        # 풀 고갈 시 30초 대기 대신 10초 후 빠르게 실패
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
