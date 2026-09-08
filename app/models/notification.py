from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PushToken(Base, TimestampMixin):
    __tablename__ = "t_push_token"
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_user_device"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("t_user.id"), nullable=False)
    push_token: Mapped[str] = mapped_column(String(500), nullable=False)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(Enum("ios", "android"), nullable=False)
    is_active: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=True)
    # 앱/기기 상태 (2026-09-08, 학생 앱 t_push_token과 같은 컬럼 구성) — 토큰 등록 때 앱이 함께 보냄. 구버전 앱은 안 보내므로 nullable.
    app_version: Mapped[str | None] = mapped_column(String(20), nullable=True)     # "1.3.0"
    build_number: Mapped[str | None] = mapped_column(String(20), nullable=True)    # Android versionCode / iOS buildNumber
    ota: Mapped[str | None] = mapped_column(String(32), nullable=True)             # 'embedded' | 'YYYYMMDD-HHMM' (실행 중 OTA의 ET 발행시각)
    update_id: Mapped[str | None] = mapped_column(String(40), nullable=True)       # expo-updates updateId (OTA일 때만)
    device_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True) # 마지막 토큰 등록(앱 실행) 시각, ET


class NotificationLog(Base, TimestampMixin):
    __tablename__ = "t_notification_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("t_user.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "sent", "failed"), nullable=False, default="pending"
    )
    push_response: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NotificationRecipient(Base, TimestampMixin):
    __tablename__ = "t_notification_recipient"
    __table_args__ = (UniqueConstraint("notification_id", "user_id", name="uq_notif_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_notification_log.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("t_user.id"), nullable=False)
    is_read: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
