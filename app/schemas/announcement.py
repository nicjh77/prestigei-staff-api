from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TargetRole = Literal["all", "staff", "manager"]
Priority = Literal["normal", "high", "urgent"]


class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=300)
    content: str
    target_role: TargetRole = "all"
    priority: Priority = "normal"
    publish_at: datetime | None = None
    expire_at: datetime | None = None


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(None, max_length=300)
    content: str | None = None
    target_role: TargetRole | None = None
    priority: Priority | None = None
    publish_at: datetime | None = None
    expire_at: datetime | None = None


class AnnouncementOut(BaseModel):
    id: int
    title: str
    content: str
    target_role: str
    priority: str
    publish_at: datetime | None
    expire_at: datetime | None
    is_read: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    count: int
