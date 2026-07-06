from datetime import date

from pydantic import BaseModel


class PostCreate(BaseModel):
    title: str
    details: str | None = None
    bid: str | None = None


class PostUpdate(BaseModel):
    title: str | None = None
    details: str | None = None


class PostOut(BaseModel):
    id: int
    bid: str | None
    title: str
    details: str | None
    regdate: date | None
    wid: int | None
    delyn: str

    model_config = {"from_attributes": True}
