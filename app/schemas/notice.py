from pydantic import BaseModel


class NoticeListItem(BaseModel):
    id: int
    regdate: str | None
    branch: str
    title: str


class NoticeDetail(BaseModel):
    id: int
    regdate: str | None
    title: str
    branch: str
    details: str | None
    noticed_by: str | None
