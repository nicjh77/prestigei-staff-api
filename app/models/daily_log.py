from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyCategory(Base):
    __tablename__ = "t_daily_category"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shortcode: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ins_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ins_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    upd_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upd_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DailyLogTask(Base):
    __tablename__ = "t_daily_log_task"

    taskid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    term_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    startdate: Mapped[date] = mapped_column(Date, nullable=False)
    targetdate: Mapped[date] = mapped_column(Date, nullable=False)
    completed: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    sid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ins_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ins_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    upd_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upd_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DailyLog(Base):
    __tablename__ = "t_daily_log"

    logid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    logdate: Mapped[date | None] = mapped_column(Date, nullable=True)
    taskid: Mapped[int] = mapped_column(Integer, nullable=False)
    dailylog: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ins_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ins_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    upd_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upd_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
