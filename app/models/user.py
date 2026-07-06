from datetime import datetime

from sqlalchemy import BigInteger, CHAR, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "t_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wid: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 출퇴근 연결키
    loginid: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_kname: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_ename: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(45), nullable=True)
    del_yn: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="N")
    bid: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 지점
    tid: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 선생님
    last_access_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    num_of_access: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ins_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


    @property
    def is_active(self) -> bool:
        return self.del_yn == "N"


class RefreshToken(Base):
    __tablename__ = "t_refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

