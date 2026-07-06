from datetime import datetime

from pydantic import BaseModel


class WeeklyVisionListOut(BaseModel):
    id: int
    title: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class WeeklyVisionOut(BaseModel):
    id: int
    title: str | None
    content: str | None
    created_at: datetime | None
    created_by: int | None
    updated_at: datetime | None
    updated_by: int | None

    model_config = {"from_attributes": True}
