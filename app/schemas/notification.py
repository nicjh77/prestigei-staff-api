from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PushTokenRegister(BaseModel):
    push_token: str
    device_id: str
    platform: Literal["ios", "android"]


class SendNotificationRequest(BaseModel):
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
