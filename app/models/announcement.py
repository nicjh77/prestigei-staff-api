from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    target_role: Mapped[str] = mapped_column(
        Enum("all", "staff", "manager"), nullable=False, default="all"
    )
    priority: Mapped[str] = mapped_column(
        Enum("normal", "high", "urgent"), nullable=False, default="normal"
    )
    publish_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    author: Mapped["User"] = relationship()  # noqa: F821
    reads: Mapped[list["AnnouncementRead"]] = relationship(back_populates="announcement", cascade="all, delete-orphan")


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    announcement_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("announcements.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_user.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    announcement: Mapped["Announcement"] = relationship(back_populates="reads")
