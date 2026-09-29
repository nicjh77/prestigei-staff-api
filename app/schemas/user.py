from datetime import datetime

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    id: int
    wid: int | None
    loginid: str | None
    user_kname: str | None
    user_ename: str | None
    user_role: str | None
    email: str | None
    phone: str | None
    bid: int | None
    tid: int | None

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    # t_user 컬럼 폭 (varchar 200/200/200/45) — 넘기면 422. 없으면 커밋(응답 뒤)에서 터져 200 을 받고도 저장이 안 된다
    user_kname: str | None = Field(None, max_length=200)
    user_ename: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=45)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
