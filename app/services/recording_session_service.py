from datetime import date

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from dataclasses import dataclass

from fastapi import HTTPException

from app.models.user import User
from app.schemas.recording import BranchAccessOut, BranchOut, RecordingSessionOut

# LMS recording 사이트(recording.prestigei.com, server.js)의 /api/tutor-schedules · /api/class-schedules SQL을 그대로 옮긴 것.
# 차이: 날짜 제한(오늘~내일)은 앱이 담당(어제/오늘/내일 칩), 지점은 bid int 로 받고, 로그인 교사의 일정(mine)을 앞에 둔다.
# 읽기 전용 — 일정 데이터는 LMS 소유.
#
# 지점 접근 범위 (test-report 와 같은 규칙, 오너 2026-09-25): 접근 가능 지점 = 본인 t_user.bid ∪ t_permission_income(memid=user.id).branch(shortname).
# 'HQ' 권한 행이 있거나 본사(bid 6) 소속이면 전 지점(view_all). 다른 지점은 목록에 아예 안 나오고 요청하면 403.
# 기본 선택은 본인 소속, HQ 소속만 전체(본사엔 수업·튜터링이 없다). 권한은 LMS 가 t_permission_income 에서 관리 — 앱은 읽기만.
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
_PERM_SQL = text("SELECT branch FROM t_permission_income WHERE memid = :memid")
HQ_BID = 6


@dataclass(frozen=True)
class BranchAccess:
    view_all: bool
    bids: frozenset[int]        # view_all 이 아닐 때 접근 가능한 지점
    branches: list[BranchOut]   # 접근 가능한 지점 (표시용, 이름순)
    home_bid: int | None


async def branch_access(db: AsyncSession, user: User) -> BranchAccess:
    all_rows = (await db.execute(_BRANCH_SQL)).all()
    by_short = {r.shortname: r.bid for r in all_rows if r.shortname}
    perms = (await db.execute(_PERM_SQL, {"memid": user.id})).all()
    view_all = user.bid == HQ_BID
    bids: set[int] = set()
    if user.bid is not None:
        bids.add(user.bid)                       # 본인 소속은 항상 포함
    for p in perms:
        sn = str(p.branch or "").strip()
        if sn == "HQ":
            view_all = True
        elif sn in by_short:
            bids.add(by_short[sn])
    branches = [BranchOut(bid=r.bid, name=r.fullname or str(r.bid), short=r.shortname) for r in all_rows if view_all or r.bid in bids]
    return BranchAccess(view_all=view_all, bids=frozenset(bids), branches=branches, home_bid=user.bid)


async def list_branches(db: AsyncSession, user: User) -> BranchAccessOut:
    acc = await branch_access(db, user)
    return BranchAccessOut(branches=acc.branches, home_bid=acc.home_bid, view_all=acc.view_all, default_all=acc.home_bid == HQ_BID)


def resolve_bid_filter(acc: BranchAccess, bid: int | None) -> tuple[bool, list[int]]:
    """요청 bid(None=기본, 0=접근 가능 전체, n=특정) → (all_bids, bids). 범위 밖이면 403.
    기본: 본인 소속(HQ 소속은 전체)."""
    if bid is None:
        if acc.home_bid == HQ_BID:
            return (True, [])
        return (False, [acc.home_bid] if acc.home_bid is not None else sorted(acc.bids))
    if bid == 0:
        return (True, []) if acc.view_all else (False, sorted(acc.bids))
    if not acc.view_all and bid not in acc.bids:
        raise HTTPException(status_code=403, detail="You don't have access to that branch")
    return (False, [bid])


def _hhmm(v) -> str | None:
    if v is None or v == "":
        return None
    t = str(v)
    return t[:5] if len(t) >= 5 else t


async def list_sessions(db: AsyncSession, user: User, kind: str, d: date, bid: int | None) -> list[RecordingSessionOut]:
    my_tid = user.tid
    all_bids, bids = resolve_bid_filter(await branch_access(db, user), bid)
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
