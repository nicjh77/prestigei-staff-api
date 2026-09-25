from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.recording import BranchOut, RecordingSessionOut

# LMS recording 사이트(recording.prestigei.com, server.js)의 /api/tutor-schedules · /api/class-schedules SQL을 그대로 옮긴 것.
# 차이: 날짜 제한(오늘~내일)은 앱이 담당(어제/오늘/내일 칩), 지점은 bid int 로 받고, 로그인 교사의 일정(mine)을 앞에 둔다.
# 읽기 전용 — 일정 데이터는 LMS 소유.

_TUTOR_SQL = text("""
    SELECT
        CONCAT(IFNULL(CONCAT('[', d.alias, ']-'), ''), b.fullname) AS title,
        a.scid, a.sid, a.tid, a.bid,
        b.fullname AS student,
        d.fullname AS teacher,
        c.shortname AS branch,
        a.scdate, a.stime, a.etime, a.memo,
        CASE WHEN e.attendance_name = 'Scheduled'
              AND STR_TO_DATE(CONCAT(a.scdate, ' ', IFNULL(a.etime, '23:00')), '%Y-%m-%d %H:%i') < NOW()
             THEN 'Not checked' ELSE e.attendance_name END AS attendance,
        CASE WHEN CONCAT(a.scdate, ' ', a.stime) < NOW() THEN 1 ELSE 0 END AS past
    FROM t_tutorschedule a
        JOIN t_studentmain b ON a.sid = b.sid
        JOIN t_branch c ON a.bid = c.bid
        LEFT JOIN t_teacher d ON a.tid = d.tid
        LEFT JOIN t_attendancetype e ON a.attendance = e.attendance
    WHERE a.scdate = :d
      AND (:bid IS NULL OR a.bid = :bid)
    ORDER BY c.fullname, a.stime
""")

_CLASS_SQL = text("""
    SELECT
        b.cid, a.cdid, t.ctid, t.tid, b.bid,
        c.shortname AS branch,
        CASE WHEN IFNULL(b.classname, '') <> '' THEN b.classname ELSE CONCAT(d.scode, '-', d.sname) END AS title,
        IFNULL(t.stime, a.stime) AS stime,
        IFNULL(t.etime, a.etime) AS etime,
        v.fullname AS teacher,
        a.sdate,
        CASE WHEN IFNULL(IFNULL(t.etime, a.etime), '') = '' THEN 0
             WHEN CONCAT(a.sdate, ' ', IFNULL(IFNULL(t.etime, a.etime), '23:00')) < NOW() THEN 1 ELSE 0 END AS past
    FROM t_classdate a
        JOIN t_classmain b ON a.cid = b.cid
        LEFT JOIN t_classteacher t ON a.cid = t.cid AND a.sdate = t.sdate AND t.stime <> ''
        LEFT JOIN t_teacher v ON t.tid = v.tid
        JOIN t_branch c ON b.bid = c.bid
        JOIN t_subject d ON b.scode = d.scode
    WHERE a.sdate = :d AND b.activeyn = 'Y'
      AND (:bid IS NULL OR b.bid = :bid)
    ORDER BY IFNULL(t.stime, a.stime)
""")

_BRANCH_SQL = text("SELECT bid, fullname, shortname FROM t_branch ORDER BY fullname")


def _hhmm(v) -> str | None:
    if v is None or v == "":
        return None
    s = str(v)
    return s[:5] if len(s) >= 5 else s


async def list_branches(db: AsyncSession) -> list[BranchOut]:
    rows = (await db.execute(_BRANCH_SQL)).all()
    return [BranchOut(bid=r.bid, name=r.fullname or str(r.bid), short=r.shortname) for r in rows]


async def list_sessions(db: AsyncSession, user: User, kind: str, d: date, bid: int | None) -> list[RecordingSessionOut]:
    my_tid = user.tid
    if kind == "tutoring":
        rows = (await db.execute(_TUTOR_SQL, {"d": d, "bid": bid})).all()
        items = [
            RecordingSessionOut(
                kind="tutoring", scid=r.scid, title=r.title, teacher=r.teacher, student=r.student,
                branch=r.branch, bid=r.bid, date=str(r.scdate), start_time=_hhmm(r.stime), end_time=_hhmm(r.etime),
                attendance=r.attendance, memo=r.memo or None, past=bool(r.past),
                mine=(my_tid is not None and r.tid == my_tid),
            )
            for r in rows
        ]
    else:
        rows = (await db.execute(_CLASS_SQL, {"d": d, "bid": bid})).all()
        items = [
            RecordingSessionOut(
                kind="class", cid=r.cid, cdid=r.cdid, ctid=r.ctid, title=r.title, teacher=r.teacher, student=None,
                branch=r.branch, bid=r.bid, date=str(r.sdate), start_time=_hhmm(r.stime), end_time=_hhmm(r.etime),
                attendance=None, memo=None, past=bool(r.past),
                mine=(my_tid is not None and r.tid == my_tid),
            )
            for r in rows
        ]
    # 내 일정 먼저, 그 안에서는 원래 순서(지점·시간) 유지
    items.sort(key=lambda x: (0 if x.mine else 1))
    return items
