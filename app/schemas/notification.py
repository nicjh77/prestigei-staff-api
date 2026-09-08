from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PushTokenRegister(BaseModel):
    push_token: str
    device_id: str
    platform: Literal["ios", "android"]
    # 앱/기기 상태 (2026-09-08, optional — 구버전 앱은 안 보냄; 학생 앱과 같은 필드명·폭).
    # ⚠️ max_length로 거부하지 않는다 — 참고용 값이 토큰 등록을 막으면 안 된다. 실제 Android 폰의 os_name이
    # 20자를 넘어 등록이 막혔던 이력(학생 앱 2026-09-04) → 컬럼 폭에 맞춰 잘라서 저장.
    app_version: str | None = None
    build_number: str | None = None
    ota: str | None = None            # 'embedded' | 'YYYYMMDD-HHMM'
    update_id: str | None = None
    device_model: str | None = None
    os_name: str | None = None
    os_version: str | None = None

    _CLIENT_INFO_WIDTHS = {
        "app_version": 20, "build_number": 20, "ota": 32, "update_id": 40,
        "device_model": 80, "os_name": 20, "os_version": 30,
    }

    @model_validator(mode="after")
    def _truncate_client_info(self):
        for field, width in self._CLIENT_INFO_WIDTHS.items():
            v = getattr(self, field)
            if isinstance(v, str):
                v = v.strip()
                setattr(self, field, v[:width] if v else None)
        return self


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
