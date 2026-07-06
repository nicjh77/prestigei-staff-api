from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_log import DailyLog, DailyLogTask, DailyCategory
from app.schemas.daily_log import DailyLogOut


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
        .join(DailyLogTask, DailyLog.taskid == DailyLogTask.taskid)
        .join(DailyCategory, DailyLogTask.category_id == DailyCategory.category_id)
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
