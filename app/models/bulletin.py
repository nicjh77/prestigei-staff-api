from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BulletinPost(Base):
    __tablename__ = "t_noticeboard"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bid: Mapped[str | None] = mapped_column(String(50), nullable=True)   # 지점
    title: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    regdate: Mapped[date | None] = mapped_column(Date, nullable=True)
    wid: Mapped[int | None] = mapped_column(Integer, nullable=True)      # 작성자
    updwid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upddate: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delyn: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="N")
    attfilename1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attfileorgname1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attfilename2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attfileorgname2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attfilename3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attfileorgname3: Mapped[str | None] = mapped_column(String(200), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.delyn == "Y"
