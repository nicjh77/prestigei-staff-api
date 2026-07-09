from datetime import date as date_type

from pydantic import BaseModel


class HolidayOut(BaseModel):
    date: date_type
    name: str | None
