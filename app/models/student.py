from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StudentMain(Base):
    """t_studentmain — LMS 학생 마스터 (읽기 전용, 앱 녹음의 학생 검색용).

    soft-delete 컬럼 없음 — 삭제된 학생은 t_student_deleted 로 옮겨지므로 이 테이블의 행은 전부 현행.
    regbid = 등록 지점(t_branch.bid), entgrade = 등록 시 학년.
    """

    __tablename__ = "t_studentmain"

    sid: Mapped[int] = mapped_column(Integer, primary_key=True)
    fullname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entgrade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regbid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    register_date: Mapped[date | None] = mapped_column(Date, nullable=True)
