from datetime import date, datetime

from pydantic import BaseModel


class DailyLogOut(BaseModel):
    logid: int
    logdate: date | None
    taskid: int
    dailylog: str | None
    completed: int | None
    task_description: str | None = None
    category_shortcode: str | None = None
    category_description: str | None = None
    ins_date: datetime | None = None
