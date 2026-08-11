from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PushTokenRegister(BaseModel):
    push_token: str
    device_id: str
    platform: Literal["ios", "android"]


class SendNotificationRequest(BaseModel):
    # extra="forbid": 알 수 없는 필드가 오면 422로 거부한다.
    # user_ids 키를 오타 내면("user_idsONE" 등) 필드 누락 → None → **전 직원 브로드캐스트**가
    # 되는 사고가 실제로 났다 (2026-08-11). 오타는 무시가 아니라 에러여야 한다.
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., max_length=300)
    body: str = Field(..., max_length=10000)
    user_ids: list[int] | None = Field(None, max_length=5000)  # None = broadcast to all
    data: dict | None = None


class NotificationItem(BaseModel):
    id: int
    notification_id: int
    title: str
    body: str
    data: dict | None = None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int
