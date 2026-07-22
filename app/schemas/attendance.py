from datetime import date as date_type, datetime
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


# 오늘의 휴일/휴가 정보 — 홈 화면 안내용 (휴일이어도 스캔은 차단하지 않음)
class DayInfo(BaseModel):
    is_holiday: bool
    holiday_name: str | None
    is_day_off: bool
    day_off_all_day: bool | None      # 종일 휴가 여부 (휴가 아닐 땐 null)
    day_off_stime: str | None         # 부분 휴가 시작 (HH:MM)
    day_off_etime: str | None
    day_off_name: str | None          # eventname


# 하루 안의 개별 in/out 쌍 (하루 여러 행 허용 — LMS와 동일)
class AttendancePair(BaseModel):
    id: int
    checkin: datetime
    checkout: datetime | None         # 미완료(퇴근 전)면 null

    model_config = {"from_attributes": True}


class TodayAttendance(BaseModel):
    checkin: datetime | None          # 첫 출근 (구버전 앱 호환)
    checkout: datetime | None         # 마지막 행의 퇴근 (미완료면 null)
    records: list[AttendancePair] = []  # 오늘 전체 기록, checkin 오름차순
    day_info: DayInfo | None = None   # additive — 기존 클라이언트는 무시


class AttendanceDay(BaseModel):
    date: date_type
    status: Literal["worked", "holiday", "dayoff", "none"]
    checkin: datetime | None          # 첫 출근 (구버전 앱 호환)
    checkout: datetime | None         # 마지막 행의 퇴근
    records: list[AttendancePair] = []  # 해당 일 전체 기록, checkin 오름차순
    holiday_name: str | None          # 휴일이면 이름 (worked여도 병기 — "휴일 근무")
    day_off: bool
    day_off_all_day: bool | None
    day_off_stime: str | None
    day_off_etime: str | None
    day_off_name: str | None


class CalendarSummary(BaseModel):
    worked_days: int
    holiday_days: int
    dayoff_days: int


class AttendanceCalendarResponse(BaseModel):
    year: int
    month: int
    days: list[AttendanceDay]         # 해당 월 전체 날짜 (1일~말일)
    summary: CalendarSummary


# 키오스크 이름 검색 → 직원 선택 시 호출
class ManualScanRequest(BaseModel):
    wid: int = Field(..., gt=0)               # User.id
    ip: str | None = Field(None, max_length=45)
    device: str | None = Field(None, max_length=255)
