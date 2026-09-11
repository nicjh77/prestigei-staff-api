from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, Field, model_validator

PtoType = Literal["dayoff", "personal", "other"]
DayOffSubType = Literal["personal", "sick", "bereavement"]
# allday=종일 08-17 / am=오전반차 08-12 / pm=오후반차 13-17 / custom=시간 지정
PtoMode = Literal["allday", "am", "pm", "custom"]

_TIME = dict(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", max_length=5)


def _check_custom_times(mode: str | None, stime: str | None, etime: str | None) -> None:
    if mode == "custom":
        if not stime or not etime:
            raise ValueError("stime and etime are required for custom mode")
        if stime >= etime:
            raise ValueError("stime must be earlier than etime")
    elif mode is None and (stime or etime):
        raise ValueError("mode='custom' is required when stime/etime are given")


class PtoDay(BaseModel):
    date: date_type
    mode: PtoMode = "allday"
    stime: str | None = Field(None, **_TIME)
    etime: str | None = Field(None, **_TIME)

    @model_validator(mode="after")
    def _validate(self):
        _check_custom_times(self.mode, self.stime, self.etime)
        return self


class PtoCreate(BaseModel):
    eventtype: PtoType
    eventname: str = Field("", max_length=255)
    dayofftype: DayOffSubType | None = None  # eventtype='dayoff'일 때만 — 미지정 시 'personal' 기본
    days: list[PtoDay] = Field(..., min_length=1, max_length=31)

    @model_validator(mode="after")
    def _unique_dates(self):
        dates = [d.date for d in self.days]
        if len(dates) != len(set(dates)):
            raise ValueError("duplicate dates in request")
        return self


class PtoUpdate(BaseModel):
    eventtype: PtoType | None = None
    eventname: str | None = Field(None, max_length=255)
    dayofftype: DayOffSubType | None = None  # eventtype='dayoff'일 때만 의미
    date: date_type | None = None
    mode: PtoMode | None = None
    stime: str | None = Field(None, **_TIME)
    etime: str | None = Field(None, **_TIME)

    @model_validator(mode="after")
    def _validate(self):
        _check_custom_times(self.mode, self.stime, self.etime)
        return self


class PtoItem(BaseModel):
    schid: int
    date: date_type
    eventtype: str
    eventname: str
    dayofftype: str | None       # personal/sick/bereavement (dayoff 하위)
    mode: PtoMode
    stime: str | None
    etime: str | None
    allday: str                 # 원본 컬럼 (Y/N)
    halfday: str | None         # 원본 컬럼 (N/A/P)
    days: float                 # LMS 공식 사용일수 (dayoff만 잔여에 집계됨)
    editable: bool              # date >= 오늘(ET) — 과거는 LMS에서만 수정


class SkippedHoliday(BaseModel):
    date: date_type
    name: str | None


class PtoCreateResponse(BaseModel):
    items: list[PtoItem]                 # 실제 생성된 행
    skipped: list[SkippedHoliday] = []   # dayoff에서 휴일이라 자동 제외된 날짜 (LMS와 동일 규칙)


class PtoBalance(BaseModel):
    year: int
    # Vacation + Personal 풀 (personal/legacy-null 사용)
    assigned: float             # vacationday + personalday
    used: float                 # dayofftype in (null, 'personal') 사용일수
    remaining: float            # assigned - used
    # 개별 배정
    vacation_assigned: float
    personal_assigned: float
    # Sick 풀
    sick_assigned: float
    sick_used: float
    sick_remaining: float
    # Bereavement (배정 없음, 사용만 추적)
    bereavement_used: float
    # 표시용
    from_date: date_type | None
    to_date: date_type | None


class PtoListResponse(BaseModel):
    year: int
    balance: PtoBalance
    items: list[PtoItem]        # 해당 연도 내 PTO 전체 (dayoff/personal/other), date 오름차순
