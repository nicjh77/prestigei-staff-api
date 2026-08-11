from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.constants import now_et


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    # ET 벽시계 naive — 전 테이블 공통 규약 (2026-08-12 UTC에서 통일, constants.now_et 참조)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_et, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_et, onupdate=now_et, nullable=False
    )
