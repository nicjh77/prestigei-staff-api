"""변환 텍스트를 LMS 녹취 테이블에 저장 (웹 recording 사이트와 같은 규칙, 오너 확정 2026-09-25).

- Tutoring → t_tutor_record(scid)   / Class → t_class_record(cid, cdid, ctid — 없으면 0, 웹과 동일)
  · 일정당 행 1개: 없으면 INSERT, 있으면 기존 transcript 뒤에 이어붙임 (웹의 "이전 녹취 불러오기 → 이어서" 경로)
  · submitdate 가 찍힌 행은 잠김 → 409 (웹도 수정 불가). 제출은 LMS 몫, 앱은 upddate 만 갱신.
- Counseling → t_meeting_record(sessionid = 시작시각 yyyymmddhhmi, sessionmemo = 학생명 또는 '') 매번 새 행.
  같은 분에 두 건이면 sessionid 에 초까지 붙여 구분.
- generated / sentdate / sentto 는 LMS 몫 — 건드리지 않는다 (`generated` 는 MySQL 예약어).
- 중복 방지: client_id(앱 항목 id) 별 결과를 1시간 기억 → 재전송이면 다시 쓰지 않고 이전 결과 반환.
  (LMS 테이블에 유니크 제약이 없어 서버가 막아야 한다.)
"""
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import now_et
from app.schemas.transcript import TranscriptSaveIn, TranscriptSaveOut

_recent: dict[str, tuple[float, TranscriptSaveOut]] = {}
_RECENT_TTL = 3600
APPEND_SEPARATOR = "\n\n"


def _remember(key: str, out: TranscriptSaveOut) -> TranscriptSaveOut:
    now = time.monotonic()
    for k in [k for k, (t, _) in _recent.items() if now - t > _RECENT_TTL]:
        _recent.pop(k, None)
    _recent[key] = (now, out)
    return out


async def _upsert_linked(db: AsyncSession, table: str, where: str, params: dict, transcript: str, insert_cols: str, insert_vals: str) -> TranscriptSaveOut:
    row = (await db.execute(text(f"SELECT id, transcript, submitdate FROM {table} WHERE {where} ORDER BY id DESC LIMIT 1"), params)).first()
    ts = now_et()
    if row is None:
        r = await db.execute(text(f"INSERT INTO {table} ({insert_cols}, transcript, upddate) VALUES ({insert_vals}, :t, :ts)"), {**params, "t": transcript, "ts": ts})
        return TranscriptSaveOut(table=table, id=int(r.lastrowid), action="inserted")
    if row.submitdate is not None:
        raise HTTPException(status_code=409, detail="This session's transcript was already submitted in the LMS and is locked")
    existing = (row.transcript or "").rstrip()
    merged = f"{existing}{APPEND_SEPARATOR}{transcript}" if existing else transcript
    await db.execute(text(f"UPDATE {table} SET transcript = :t, upddate = :ts WHERE id = :id"), {"t": merged, "ts": ts, "id": row.id})
    return TranscriptSaveOut(table=table, id=int(row.id), action="appended" if existing else "inserted")


async def _assert_session_exists(db: AsyncSession, data: TranscriptSaveIn) -> None:
    """앱이 보낸 일정 키가 실제 LMS 일정인지 — 임의 숫자로 쓰레기 행이 생기지 않게 (웹은 검증 없음, 앱은 한다)."""
    if data.type == "tutoring":
        ok = (await db.execute(text("SELECT 1 FROM t_tutorschedule WHERE scid = :scid LIMIT 1"), {"scid": data.scid})).first()
        if not ok:
            raise HTTPException(status_code=404, detail="Tutoring session not found")
    elif data.type == "class":
        ok = (await db.execute(text("SELECT 1 FROM t_classdate WHERE cid = :cid AND cdid = :cdid LIMIT 1"), {"cid": data.cid, "cdid": data.cdid})).first()
        if not ok:
            raise HTTPException(status_code=404, detail="Class date not found")


async def save_transcript(db: AsyncSession, user_id: int, data: TranscriptSaveIn) -> TranscriptSaveOut:
    key = f"{user_id}:{data.client_id}"          # 사용자별로 격리 — 다른 사람의 client_id 를 재생해도 남의 결과가 안 보인다
    cached = _recent.get(key)
    if cached:
        return cached[1].model_copy(update={"action": "duplicate"})

    if data.type == "tutoring":
        if data.scid is None:
            raise HTTPException(status_code=422, detail="scid is required for tutoring")
        await _assert_session_exists(db, data)
        out = await _upsert_linked(db, "t_tutor_record", "scid = :scid", {"scid": data.scid}, data.transcript, "scid", ":scid")
    elif data.type == "class":
        if data.cid is None or data.cdid is None:
            raise HTTPException(status_code=422, detail="cid and cdid are required for class")
        await _assert_session_exists(db, data)
        params = {"cid": data.cid, "cdid": data.cdid, "ctid": data.ctid or 0}
        out = await _upsert_linked(db, "t_class_record", "cid = :cid AND cdid = :cdid AND IFNULL(ctid, 0) = :ctid", params,
                                   data.transcript, "cid, cdid, ctid", ":cid, :cdid, :ctid")
    else:
        started = datetime.fromisoformat(data.started_at)
        sessionid = started.strftime("%Y%m%d%H%M")
        exists = (await db.execute(text("SELECT 1 FROM t_meeting_record WHERE sessionid = :s LIMIT 1"), {"s": sessionid})).first()
        if exists:
            sessionid = started.strftime("%Y%m%d%H%M%S")
        r = await db.execute(
            text("INSERT INTO t_meeting_record (sessionid, sessionmemo, transcript, upddate) VALUES (:s, :m, :t, :ts)"),
            {"s": sessionid, "m": (data.student_name or "").strip(), "t": data.transcript, "ts": now_et()},
        )
        out = TranscriptSaveOut(table="t_meeting_record", id=int(r.lastrowid), action="inserted", sessionid=sessionid)
    return _remember(key, out)
