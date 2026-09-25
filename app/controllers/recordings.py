import os
import tempfile
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import APP_TZ
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.recording import BranchOut, RecordingSessionOut
from app.schemas.transcribe import TranscribeJobOut
from app.schemas.transcript import TranscriptSaveIn, TranscriptSaveOut
from app.services import azure_speech_service, recording_session_service, transcribe_job_service, transcript_service

# 앱 Recording API. 음성은 서버에 **저장하지 않는다** (2026-09-25 오너 결정, LMS 서버 사정):
#  앱 → POST /transcribe (파일) → 서버가 임시 파일로 받아 Azure 에 넘기고 즉시 삭제 → 앱이 GET /transcribe/{job} 폴링 → 텍스트.
#  (앱→Azure 직접은 불가: Fast Transcription 은 구독 키만 받고 STS 토큰을 거부 — azure_speech_service 참조)
router = APIRouter(tags=["Recordings"])


def _today() -> date:
    return datetime.now(APP_TZ).date()


@router.get("/branches", response_model=list[BranchOut])
async def branches(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """일정 선택 시트의 지점 목록 (전 지점)."""
    return await recording_session_service.list_branches(db)


@router.get("/sessions", response_model=list[RecordingSessionOut])
async def sessions(
    type: str = Query(..., pattern="^(tutoring|class)$"),
    date_: date | None = Query(None, alias="date", description="기본 오늘(ET)"),
    bid: int | None = Query(None, description="지점. 생략 = 내 지점, 0 = 전체"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tutoring(t_tutorschedule) / Class(t_classdate) 일정 목록 — 녹음을 어느 일정에 붙일지 고르는 용도.
    LMS recording 사이트의 목록과 같은 SQL. 로그인 사용자가 담당 교사인 일정(mine)이 앞에 온다."""
    d = date_ or _today()
    if bid is None:
        bid_filter = current_user.bid
    elif bid == 0:
        bid_filter = None
    else:
        bid_filter = bid
    return await recording_session_service.list_sessions(db, current_user, type, d, bid_filter)



def _job_out(job) -> TranscribeJobOut:
    return TranscribeJobOut(job_id=job.id, status=job.status, transcript=job.transcript, duration_ms=job.duration_ms, error=job.error)


@router.post("/transcribe", response_model=TranscribeJobOut, status_code=202)
async def transcribe(
    background: BackgroundTasks,
    audio: UploadFile = File(..., description="녹음 파일 (m4a/wav/mp3, ≤300MB, ≤2h)"),
    language: str = Form("en-US", description="ko-KR | en-US | ja-JP | zh-CN | es-ES | fr-FR | de-DE"),
    mode: str = Form("conversation", pattern="^(speech|conversation)$", description="speech=단일 화자, conversation=화자 분리"),
    max_speakers: int = Form(2, ge=2, le=8, description="conversation 일 때 최대 화자 수 (상담·튜터링 2, 수업 4)"),
    current_user: User = Depends(get_current_user),
):
    """녹음 파일을 Azure 로 넘겨 텍스트로 변환하는 잡을 만든다 (202 + job_id). 파일은 변환 직후 서버에서 삭제.
    결과는 GET /recordings/transcribe/{job_id} 로 폴링. 텍스트 형식은 LMS recording 사이트와 동일."""
    if not azure_speech_service.is_configured():
        raise HTTPException(status_code=503, detail="Azure Speech is not configured")
    suffix = os.path.splitext(audio.filename or "")[1] or ".m4a"
    fd, tmp_path = tempfile.mkstemp(prefix="rec_", suffix=suffix)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > azure_speech_service.MAX_AUDIO_BYTES:
                    raise HTTPException(status_code=413, detail="Audio file too large (max 300MB)")
                out.write(chunk)
    except Exception:
        try: os.remove(tmp_path)
        except OSError: pass
        raise
    if size == 0:
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail="Empty audio file")
    job = transcribe_job_service.create(current_user.id)
    background.add_task(
        transcribe_job_service.run, job, tmp_path, audio.filename or f"audio{suffix}",
        audio.content_type or "application/octet-stream", language, mode == "conversation", max_speakers,
    )
    return _job_out(job)


@router.get("/transcribe/{job_id}", response_model=TranscribeJobOut)
async def transcribe_status(job_id: str, current_user: User = Depends(get_current_user)):
    """변환 잡 상태. 본인 잡만. 프로세스 재시작으로 사라졌으면 404 → 앱이 파일을 다시 올린다."""
    job = transcribe_job_service.get(job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcription job not found (expired or server restarted)")
    return _job_out(job)


@router.post("/transcript", response_model=TranscriptSaveOut)
async def save_transcript(
    data: TranscriptSaveIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """변환된 텍스트를 LMS 녹취 테이블에 저장 — tutoring→t_tutor_record(scid, 이어붙임), class→t_class_record(cid,cdid,ctid),
    counseling→t_meeting_record(새 행). 제출(submitdate)된 일정은 409. 같은 client_id 재전송은 중복 저장 없이 이전 결과."""
    return await transcript_service.save_transcript(db, data)
