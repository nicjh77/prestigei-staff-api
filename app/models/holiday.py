from datetime import date

from sqlalchemy import CHAR, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BranchHoliday(Base):
    """t_holiday — 지점별 휴일 (LMS Staff Schedule > Manage Holidays). bid는 int(t_branch.bid), 행당 지점 1개."""
    __tablename__ = "t_holiday"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sdate: Mapped[date] = mapped_column(Date, nullable=False)
    bid: Mapped[int] = mapped_column(Integer, nullable=False)
    holidayyn: Mapped[str | None] = mapped_column(CHAR(1), nullable=True, default="N")
    holidaynm: Mapped[str | None] = mapped_column(String(255), nullable=True)
