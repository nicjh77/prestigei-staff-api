from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Vacation(Base):
    """t_vacation — 개인별 연도별 배정 휴가 일수 (HR이 LMS Staff Vacation에서 입력, Staff API는 읽기만)"""
    __tablename__ = "t_vacation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userid: Mapped[int | None] = mapped_column(Integer, nullable=True)     # t_user.id
    ayear: Mapped[str | None] = mapped_column(CHAR(4), nullable=True)      # '2026' (char)
    fromdate: Mapped[date | None] = mapped_column(Date, nullable=True)
    todate: Mapped[date | None] = mapped_column(Date, nullable=True)
    vacationday: Mapped[float | None] = mapped_column(Float, nullable=True)
    added: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    addedby: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updatedby: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
