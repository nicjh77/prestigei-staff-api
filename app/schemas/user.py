from datetime import datetime

from pydantic import BaseModel


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
    user_kname: str | None = None
    user_ename: str | None = None
    email: str | None = None
    phone: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
