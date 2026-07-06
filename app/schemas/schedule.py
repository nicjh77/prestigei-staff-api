from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# HH:MM (stime/etime → DB String(5))
_TIME = dict(pattern=r"^\d{2}:\d{2}$", max_length=5)


class ScheduleOut(BaseModel):
    schid: int
    tid: int
    wid: int | None
    sdate: date | None
    edate: date | None
    stime: str | None
    etime: str | None
    allday: str
    eventname: str | None
    eventtype: str | None

    model_config = {"from_attributes": True}


class ScheduleCreate(BaseModel):
    tid: int
    wid: int | None = None
    sdate: date
    edate: date
    stime: str | None = Field(None, **_TIME)
    etime: str | None = Field(None, **_TIME)
    allday: Literal["Y", "N"] = "N"
    eventname: str | None = None
    eventtype: str | None = None


class ScheduleUpdate(BaseModel):
    sdate: date | None = None
    edate: date | None = None
    stime: str | None = Field(None, **_TIME)
    etime: str | None = Field(None, **_TIME)
    allday: Literal["Y", "N"] | None = None
    eventname: str | None = None
    eventtype: str | None = None
