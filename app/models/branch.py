from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Branch(Base):
    __tablename__ = "t_branch"

    bid: Mapped[int] = mapped_column(Integer, primary_key=True)
    fullname: Mapped[str | None] = mapped_column(String(255), nullable=True)
