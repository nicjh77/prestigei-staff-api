"""변환 텍스트를 LMS 녹취 테이블에 저장 (웹 recording 사이트와 같은 규칙, 오너 확정 2026-09-25).

- Tutoring → t_tutor_record(scid)   / Class → t_class_record(cid, cdid, ctid — 없으면 0, 웹과 동일)
  · 일정당 행 1개: 없으면 INSERT, 있으면 기존 transcript 뒤에 이어붙임 (웹의 "이전 녹취 불러오기 → 이어서" 경로)
  · submitdate 가 찍힌 행은 잠김 → 409 (웹도 수정 불가). 제출은 LMS 몫, 앱은 upddate 만 갱신.
- Counseling → t_meeting_record(sessionid = 시작시각 yyyymmddhhmi, sessionmemo = 학생명 또는 '') 매번 새 행.
  같은 분에 두 건이면 sessionid 에 초까지 붙여 구분.
- generated / sentdate / sentto 는 LMS 몫 — 건드리지 않는다 (`generated` 는 MySQL 예약어).
- 중복 방지: (user_id, client_id) 별 결과를 1시간 기억 → 재전송이면 다시 쓰지 않고 이전 결과 반환.
  (LMS 테이블에 유니크 제약이 없어 서버가 막아야 한다.) 기억은 컨트롤러가 **커밋 성공 후** `remember()` 로 한다.
- 권한 범위(제품 결정, 웹과 동일): 어느 직원이든 어느 지점·교사의 튜터/수업 일정에나 저장할 수 있다 — 상담사가 지점을 넘나들고
  웹 사이트도 제한이 없다. 대신 일정 키가 실제 LMS 행인지(scid / cid+cdid / ctid∈t_classteacher)는 검증한다.
"""
import asyncio
import json
import os
import tempfile
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import now_et
from app.core.database import AsyncSessionLocal
from app.schemas.transcript import TranscriptMeta, TranscriptSaveIn, TranscriptSaveOut

APPEND_SEPARATOR = "\n\n"

# ---- 저장 기록 (중복 방지) — 디스크 JSON, 30일 ----
# 서버가 변환 직후 LMS 에 저장하므로(2026-09-28) 앱은 언제든 나중에 "이 녹음 저장됐나?" 를 물을 수 있어야 하고,
# 앱이 같은 녹음을 다시 올려도 두 번 저장되면 안 된다(LMS 테이블에 유니크 제약 없음). 프로세스 메모리로는 재시작·1시간에 사라져 파일로 둔다.
_STORE_TTL_SEC = 30 * 24 * 3600
_store: dict[str, dict] | None = None
_store_lock = asyncio.Lock()


def _store_path() -> str:
    return os.path.join(tempfile.gettempdir(), "transcript_saved.json")


def _load_store() -> dict[str, dict]:
    global _store
    if _store is None:
        try:
            with open(_store_path(), encoding="utf-8") as f:
                _store = json.load(f)
        except (OSError, ValueError):
            _store = {}
    return _store


def _flush_store() -> None:
    now = time.time()
    data = {k: v for k, v in _load_store().items() if now - v.get("saved_at", now) < _STORE_TTL_SEC}
    _store.clear(); _store.update(data)
    tmp = _store_path() + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, _store_path())
    except OSError as e:
        print(f"[transcript] could not persist save index: {e}", flush=True)


def _key(user_id: int, client_id: str) -> str:
    return f"{user_id}:{client_id}"       # 사용자별 격리 — 남의 client_id 를 재생해도 남의 결과가 안 보인다


def recall(user_id: int, client_id: str) -> TranscriptSaveOut | None:
    hit = _load_store().get(_key(user_id, client_id))
    if not hit or time.time() - hit.get("saved_at", 0) > _STORE_TTL_SEC:
        return None
    return TranscriptSaveOut(table=hit["table"], id=hit["id"], action="duplicate", sessionid=hit.get("sessionid"))


def remember(user_id: int, client_id: str, out: TranscriptSaveOut) -> None:
    _load_store()[_key(user_id, client_id)] = {"table": out.table, "id": out.id, "sessionid": out.sessionid, "saved_at": time.time()}
    _flush_store()


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


async def assert_session_exists(db: AsyncSession, data: TranscriptMeta) -> None:
    """앱이 보낸 일정 키가 실제 LMS 일정인지 — 임의 숫자로 쓰레기 행이 생기지 않게 (웹은 검증 없음, 앱은 한다)."""
    if data.type == "tutoring":
        ok = (await db.execute(text("SELECT 1 FROM t_tutorschedule WHERE scid = :scid LIMIT 1"), {"scid": data.scid})).first()
        if not ok:
            raise HTTPException(status_code=404, detail="Tutoring session not found")
    elif data.type == "class":
        ok = (await db.execute(text("SELECT 1 FROM t_classdate WHERE cid = :cid AND cdid = :cdid LIMIT 1"), {"cid": data.cid, "cdid": data.cdid})).first()
        if not ok:
            raise HTTPException(status_code=404, detail="Class date not found")
        if data.ctid:
            ok = (await db.execute(text("SELECT 1 FROM t_classteacher WHERE ctid = :ctid AND cid = :cid LIMIT 1"), {"ctid": data.ctid, "cid": data.cid})).first()
            if not ok:
                raise HTTPException(status_code=404, detail="Class teacher row not found")


async def save_transcript(db: AsyncSession, data: TranscriptSaveIn) -> TranscriptSaveOut:
    """DB 쓰기만 한다. 커밋과 저장 기록은 호출자 몫 (recall → save → commit → remember)."""
    if data.type == "tutoring":
        if data.scid is None:
            raise HTTPException(status_code=422, detail="scid is required for tutoring")
        await assert_session_exists(db, data)
        out = await _upsert_linked(db, "t_tutor_record", "scid = :scid", {"scid": data.scid}, data.transcript, "scid", ":scid")
    elif data.type == "class":
        if data.cid is None or data.cdid is None:
            raise HTTPException(status_code=422, detail="cid and cdid are required for class")
        await assert_session_exists(db, data)
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
    return out


async def save_after_transcription(user_id: int, meta: TranscriptMeta, transcript: str) -> TranscriptSaveOut:
    """변환 잡이 끝난 직후 서버가 직접 LMS 에 저장 (요청 컨텍스트 밖 — 자기 세션, 명시 커밋)."""
    cached = recall(user_id, meta.client_id)
    if cached:
        return cached
    data = TranscriptSaveIn(**meta.model_dump(), transcript=transcript)
    async with _store_lock:
        async with AsyncSessionLocal() as db:
            try:
                out = await save_transcript(db, data)
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        remember(user_id, meta.client_id, out)
    return out
