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
    connect_args={"connect_timeout": 5},   # DB 호스트 무응답 시 OS TCP 타임아웃(분 단위) 대신 5초 후 실패
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """요청당 세션. **반드시 `Depends(get_db, scope="function")` 으로 주입** (QA 2026-09-29): FastAPI 0.118+ 기본 scope 는 yield 이후
    코드(= 이 커밋)를 응답을 보낸 **뒤**에 실행하므로, 커밋이 실패해도(컬럼 길이 초과·커넥션 끊김·데드락) 클라이언트는 이미 200 을 받은
    상태였다. scope="function" 이면 커밋이 응답 전에 끝나 실패가 500 으로 전달된다. 백그라운드 작업은 어차피 자기 세션을 쓴다."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
