from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import PTO_EVENT_TYPES
from app.models.schedule import Schedule
from app.models.user import User


def subject_filter(user: User):
    """내 일정 판정 (2026-09-05 오너 확인 규칙).

    - PTO(dayoff/personal/other): LMS Staff Schedule이 대상자를 tid = t_user.id 로 저장 (uid/wid는 작성자).
    - 티처 수업 일정(class/tutor 등): tid = t_teacher.tid (t_user.tid로 연결).
    uid는 작성자라 매칭에 쓰지 않는다 — 쓰면 관리자가 대신 입력한 타인 일정이 관리자 본인 것으로 보인다.
    한계: t_teacher.tid와 t_user.id는 숫자 범위가 겹치고(1~263 vs 2~), 과거 Instructor 화면에서
    t_teacher.tid로 넣은 dayoff 행은 티처 유저에게 안 보인다 — 수용 (PTO는 Staff Schedule에서만 입력).
    """
    conds = [and_(Schedule.tid == user.id, Schedule.eventtype.in_(PTO_EVENT_TYPES))]
    if user.tid is not None:
        conds.append(and_(
            Schedule.tid == user.tid,
            or_(Schedule.eventtype.is_(None), Schedule.eventtype.not_in(PTO_EVENT_TYPES)),
        ))
    return or_(*conds)


async def get_schedule(db: AsyncSession, user: User, from_date: date, to_date: date) -> list[Schedule]:
    # 기간 겹침 판정: sdate~edate 범위가 조회 구간과 겹치면 포함 (edate 없으면 단일일)
    result = await db.execute(
        select(Schedule).where(
            subject_filter(user),
            Schedule.sdate <= to_date,
            func.coalesce(Schedule.edate, Schedule.sdate) >= from_date,
        ).order_by(Schedule.sdate)
    )
    return result.scalars().all()
