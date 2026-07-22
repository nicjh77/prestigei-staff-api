from pydantic import BaseModel


class LoginRequest(BaseModel):
    user_id: str
    password: str
    device_id: str | None = None


class UserInfo(BaseModel):
    id: int
    loginid: str | None
    email: str | None
    user_ename: str | None
    user_role: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
