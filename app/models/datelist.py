from datetime import date

from sqlalchemy import CHAR, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DateList(Base):
    """t_datelist — 날짜 차원 테이블 (날짜당 1행, 휴일이면 holidayyn='Y')"""
    __tablename__ = "t_datelist"

    sdate: Mapped[date] = mapped_column(Date, primary_key=True)
    weekday: Mapped[str | None] = mapped_column(String(20), nullable=True)
    holidayyn: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="N")
    holidaynm: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # JSON 배열 문자열 (t_invoiceitem.bid 형식, 예: '["6","7"]') — NULL = 전 지점 공통
    bid: Mapped[str | None] = mapped_column(String(255), nullable=True)
