from datetime import date

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.recording import BranchOut, RecordingSessionOut

# LMS recording 사이트(recording.prestigei.com, server.js)의 /api/tutor-schedules · /api/class-schedules SQL을 그대로 옮긴 것.
# 차이: 날짜 제한(오늘~내일)은 앱이 담당(어제/오늘/내일 칩), 지점은 bid int 로 받고, 로그인 교사의 일정(mine)을 앞에 둔다.
# 읽기 전용 — 일정 데이터는 LMS 소유.
#
# 지점 접근 범위 (오너 확정 2026-09-25): HQ(bid 6) 사용자는 전 지점, 그 외는 본인 t_user.bid 만. 다른 지점은 목록에 아예 안 나온다.
# 멀티 지점 사용자는 settings.RECORDING_MULTI_BRANCH_USERS 예외 (DB 에 사용자-지점 매핑이 없어서).

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
      AND (:all_bids OR a.bid IN :bids)
    ORDER BY c.fullname, a.stime
""").bindparams(bindparam("bids", expanding=True))

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
      AND (:all_bids OR b.bid IN :bids)
    ORDER BY IFNULL(t.stime, a.stime)
""").bindparams(bindparam("bids", expanding=True))

_BRANCH_SQL = text("SELECT bid, fullname, shortname FROM t_branch ORDER BY fullname")
HQ_BID = 6


def _multi_branch_extras(user_id: int) -> set[int]:
    """settings.RECORDING_MULTI_BRANCH_USERS = "userId:bid,bid;userId:bid" 에서 이 사용자의 추가 지점."""
    raw = settings.RECORDING_MULTI_BRANCH_USERS.strip()
    if not raw:
        return set()
    for chunk in raw.split(";"):
        if ":" not in chunk:
            continue
        uid, bids = chunk.split(":", 1)
        if uid.strip() == str(user_id):
            return {int(b) for b in bids.split(",") if b.strip().isdigit()}
    return set()


def allowed_bids(user: User) -> set[int] | None:
    """None = 전 지점(HQ). 그 외 = 접근 가능한 지점 집합 (본인 지점 + 예외 목록)."""
    if user.bid == HQ_BID:
        return None
    bids = set()
    if user.bid is not None:
        bids.add(user.bid)
    bids |= _multi_branch_extras(user.id)
    return bids


def _hhmm(v) -> str | None:
    if v is None or v == "":
        return None
    s = str(v)
    return s[:5] if len(s) >= 5 else s


async def list_branches(db: AsyncSession, user: User) -> list[BranchOut]:
    """접근 가능한 지점만 — HQ 는 전부, 그 외는 본인(+예외) 지점."""
    allowed = allowed_bids(user)
    rows = (await db.execute(_BRANCH_SQL)).all()
    return [BranchOut(bid=r.bid, name=r.fullname or str(r.bid), short=r.shortname) for r in rows if allowed is None or r.bid in allowed]


def resolve_bid_filter(user: User, bid: int | None) -> tuple[bool, list[int]]:
    """요청 bid(None=내 지점, 0=전체, n=특정) 를 접근 범위로 좁힌다 → (all_bids, bids).
    범위 밖 지점을 요청하면 403. 전체(0)는 HQ 면 진짜 전체, 그 외는 허용 집합 전체."""
    allowed = allowed_bids(user)
    if bid is None:
        # 기본값: HQ 는 전체(본인 지점 HQ 에는 수업이 없다), 멀티 지점은 허용 집합 전체, 단일 지점은 본인 지점
        if allowed is None:
            return (True, [])
        return (False, sorted(allowed))
    if bid == 0:
        return (True, []) if allowed is None else (False, sorted(allowed))
    if allowed is not None and bid not in allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="You don't have access to that branch")
    return (False, [bid])


async def list_sessions(db: AsyncSession, user: User, kind: str, d: date, bid: int | None) -> list[RecordingSessionOut]:
    my_tid = user.tid
    all_bids, bids = resolve_bid_filter(user, bid)
    if not all_bids and not bids:
        return []
    params = {"d": d, "all_bids": all_bids, "bids": bids or [-1]}
    if kind == "tutoring":
        rows = (await db.execute(_TUTOR_SQL, params)).all()
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
        rows = (await db.execute(_CLASS_SQL, params)).all()
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
