from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_log import DailyLog, DailyLogTask, DailyCategory
from app.schemas.daily_log import DailyLogOut, TaskReportLog, TaskReportOut


async def get_daily_logs(
    db: AsyncSession, user_id: int, from_date: date, to_date: date
) -> list[DailyLogOut]:
    stmt = (
        select(
            DailyLog.logid,
            DailyLog.logdate,
            DailyLog.taskid,
            DailyLog.dailylog,
            DailyLog.completed,
            DailyLog.ins_date,
            DailyLogTask.description.label("task_description"),
            DailyCategory.shortcode.label("category_shortcode"),
            DailyCategory.description.label("category_description"),
        )
        # LEFT JOIN — 태스크/카테고리가 삭제·누락된 로그도 목록에서 사라지지 않게 (보류 항목 #2 해소)
        .outerjoin(DailyLogTask, DailyLog.taskid == DailyLogTask.taskid)
        .outerjoin(DailyCategory, DailyLogTask.category_id == DailyCategory.category_id)
        .where(
            DailyLog.ins_by == user_id,
            DailyLog.logdate >= from_date,
            DailyLog.logdate <= to_date,
        )
        .order_by(DailyLog.logdate.desc(), DailyLog.ins_date.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        DailyLogOut(
            logid=row.logid,
            logdate=row.logdate,
            taskid=row.taskid,
            dailylog=row.dailylog,
            completed=row.completed,
            task_description=row.task_description,
            category_shortcode=row.category_shortcode,
            category_description=row.category_description,
            ins_date=row.ins_date,
        )
        for row in rows
    ]


async def get_task_report(
    db: AsyncSession,
    user_id: int,
    from_date: date,
    to_date: date,
    statuses: list[str] | None,
) -> list[TaskReportOut]:
    """태스크 리포트 (LMS "Task Report"와 동일 의미).

    기간(Period)은 **로그의 logdate** 기준이다 — 기간 안에 내 로그(logdate)가 있는
    태스크만 포함하고, 각 태스크 아래에 그 기간의 내 로그를 logdate 내림차순으로 중첩한다.
    (task의 startdate/ins_date나 로그의 ins_date는 필터에 쓰지 않음 — LMS 실동작으로 확인)
    statuses가 주어지면 태스크 status로 추가 필터 (예: 기본 Planned/Scheduled + In progress).
    """
    # 1) 기간 내 내 로그 전부 (태스크별로 묶기 위해 한 번에 조회)
    log_rows = (
        await db.execute(
            select(DailyLog)
            .where(
                DailyLog.ins_by == user_id,
                DailyLog.logdate >= from_date,
                DailyLog.logdate <= to_date,
            )
            .order_by(DailyLog.logdate.desc(), DailyLog.ins_date.desc())
        )
    ).scalars().all()
    if not log_rows:
        return []

    logs_by_task: dict[int, list[DailyLog]] = {}
    for log in log_rows:
        logs_by_task.setdefault(log.taskid, []).append(log)
    task_ids = list(logs_by_task.keys())

    # 2) 해당 태스크들 (+카테고리 LEFT JOIN, status 필터)
    task_stmt = (
        select(
            DailyLogTask,
            DailyCategory.shortcode.label("category_shortcode"),
            DailyCategory.description.label("category_description"),
        )
        .outerjoin(DailyCategory, DailyLogTask.category_id == DailyCategory.category_id)
        .where(DailyLogTask.taskid.in_(task_ids))
    )
    if statuses:
        task_stmt = task_stmt.where(DailyLogTask.status.in_(statuses))
    task_rows = (await db.execute(task_stmt)).all()

    # 3) 태스크별 전체 로그 수 (기간 무관 — LMS #DailyLog 컬럼과 동일)
    count_rows = (
        await db.execute(
            select(DailyLog.taskid, func.count().label("cnt"))
            .where(DailyLog.taskid.in_(task_ids))
            .group_by(DailyLog.taskid)
        )
    ).all()
    total_by_task = {r.taskid: r.cnt for r in count_rows}

    report = [
        TaskReportOut(
            taskid=row.DailyLogTask.taskid,
            description=row.DailyLogTask.description,
            status=row.DailyLogTask.status,
            startdate=row.DailyLogTask.startdate,
            targetdate=row.DailyLogTask.targetdate,
            completed_date=row.DailyLogTask.completed,
            progress=row.DailyLogTask.progress,
            category_shortcode=row.category_shortcode,
            category_description=row.category_description,
            total_logs=total_by_task.get(row.DailyLogTask.taskid, 0),
            logs=[
                TaskReportLog(
                    logid=log.logid,
                    logdate=log.logdate,
                    dailylog=log.dailylog,
                    completed=log.completed,
                    ins_date=log.ins_date,
                )
                for log in logs_by_task[row.DailyLogTask.taskid]
            ],
        )
        for row in task_rows
    ]
    # 기간 내 가장 최근 로그가 있는 태스크가 위로
    report.sort(key=lambda t: (t.logs[0].logdate or date.min, t.logs[0].ins_date or datetime.min), reverse=True)
    return report
