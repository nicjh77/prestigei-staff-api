from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# 스캐너가 QR 읽고 서버에 전송 (e{user_id} 형식)
# 엔드포인트가 무인증(정책상 허용)이므로, 저장 남용/대용량 페이로드 방지를 위해 길이 제한
# ip/device는 DB 컬럼 크기(checkinip String(45), checkinbrowser String(255))에 맞춤
class ScanRequest(BaseModel):
    token: str = Field(..., max_length=64)
    ip: str | None = Field(None, max_length=45)
    device: str | None = Field(None, max_length=255)


# 출퇴근 기록 응답
class AttendanceRecordOut(BaseModel):
    id: int
    wid: int
    checkin: datetime | None
    checkout: datetime | None
    memo: str | None

    model_config = {"from_attributes": True}


class TodayAttendance(BaseModel):
    checkin: datetime | None
    checkout: datetime | None


class QRStatusResponse(BaseModel):
    status: Literal["pending", "checked_in", "checked_out"]


# 키오스크 이름 검색 → 직원 선택 시 호출
class ManualScanRequest(BaseModel):
    wid: int = Field(..., gt=0)               # User.id
    ip: str | None = Field(None, max_length=45)
    device: str | None = Field(None, max_length=255)
