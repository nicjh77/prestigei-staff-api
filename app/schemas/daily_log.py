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


# 태스크 리포트 (LMS "Task Report" 화면과 동일 구조) — 태스크 + 기간 내 로그 중첩
class TaskReportLog(BaseModel):
    logid: int
    logdate: date | None
    dailylog: str | None
    completed: int | None          # 1 = finished
    ins_date: datetime | None = None


class TaskReportOut(BaseModel):
    taskid: int
    description: str | None        # 태스크 설명
    status: str | None             # Planned/Scheduled | In progress | Completed | On hold | Cancelled
    startdate: date | None
    targetdate: date | None
    completed_date: date | None    # t_daily_log_task.completed (완료 처리된 날)
    progress: int | None           # 0~100
    category_shortcode: str | None = None
    category_description: str | None = None
    total_logs: int                # 태스크 전체 로그 수 (기간 무관 — LMS #DailyLog와 동일)
    logs: list[TaskReportLog]      # 조회 기간 내 내 로그, logdate 내림차순
