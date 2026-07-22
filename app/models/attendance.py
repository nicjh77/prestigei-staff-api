from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AttendanceRecord(Base):
    """t_usertimecheck — 하루 여러 행 허용(행 = in/out 쌍 1개, 2026-07-22 LMS 정합)"""
    __tablename__ = "t_usertimecheck"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wid: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # 컬럼명과 달리 t_user.id (PK) — t_user.wid 아님
    checkin: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checkout: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    upd_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    upd_wid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checkinip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    checkoutip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    checkinbrowser: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checkoutbrowser: Mapped[str | None] = mapped_column(String(255), nullable=True)
