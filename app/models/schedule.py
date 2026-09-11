from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Schedule(Base):
    __tablename__ = "t_schedule"

    schid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 대상자 키 (2026-09-05 오너 확인): PTO(dayoff/personal/other)는 tid = t_user.id,
    # 티처 수업 일정은 tid = t_teacher.tid. uid/wid는 둘 다 작성자(로그인 사용자) — 대상 아님.
    tid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uid: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 작성자 t_user.id (LMS 로그인 사용자)
    wid: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 작성자 t_user.id
    sdate: Mapped[date | None] = mapped_column(Date, nullable=True)
    edate: Mapped[date | None] = mapped_column(Date, nullable=True)
    stime: Mapped[str | None] = mapped_column(String(5), nullable=True)
    etime: Mapped[str | None] = mapped_column(String(5), nullable=True)
    allday: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="N")
    halfday: Mapped[str | None] = mapped_column(CHAR(1), nullable=True, default="N")  # N / A(오전) / P(오후)
    eventname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eventtype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dayofftype: Mapped[str | None] = mapped_column(String(50), nullable=True)  # personal/sick/bereavement (dayoff 하위)
    eventid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ins_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    upd_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
