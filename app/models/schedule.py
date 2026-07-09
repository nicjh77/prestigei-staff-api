from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Schedule(Base):
    __tablename__ = "t_schedule"

    schid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tid: Mapped[int | None] = mapped_column(Integer, nullable=True)  # t_teacher.tid (티처 일정)
    uid: Mapped[int | None] = mapped_column(Integer, nullable=True)  # t_user.id — 일반 직원 일정 대상 (2026-07 추가)
    wid: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 작성자 t_user.id (대상 아님)
    sdate: Mapped[date | None] = mapped_column(Date, nullable=True)
    edate: Mapped[date | None] = mapped_column(Date, nullable=True)
    stime: Mapped[str | None] = mapped_column(String(5), nullable=True)
    etime: Mapped[str | None] = mapped_column(String(5), nullable=True)
    allday: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="N")
    eventname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eventtype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    eventid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ins_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    upd_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
