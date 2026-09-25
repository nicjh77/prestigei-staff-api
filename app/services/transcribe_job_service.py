"""변환 잡 (in-memory, 단일 프로세스). 앱: POST 파일 → job_id 즉시 → GET 으로 폴링.

왜 BackgroundTasks 가 아니라 asyncio.create_task 인가 (리뷰 2026-09-25, HIGH):
  FastAPI 의 yield 의존성(get_db — get_current_user 가 씀)은 응답 전송 **과 BackgroundTasks 까지 끝난 뒤** 종료된다.
  즉 BackgroundTasks 로 Azure 를 부르면 인증 때 잡은 DB 커넥션이 변환 1~3분 내내 풀에서 안 풀려(트랜잭션 열린 채)
  동시 업로드 몇 건이면 pool(10+20) 이 말라 로그인·스캔까지 500 이 난다. (/notifications/send 의 1205 사고와 같은 순서 문제.)
  create_task 는 요청과 무관한 독립 태스크라 응답이 끝나는 즉시 세션이 반환된다. Task 참조는 job 에 붙여 GC 를 막는다.

제한: 사용자당 동시 1건(앱도 1건씩 보내지만 서버가 막는다), Azure 동시 호출은 세마포어 2 — 비용·대역폭 폭주 방지.
임시 파일은 Azure 호출이 끝나는 즉시 삭제 (서버에 음성을 남기지 않는다는 원칙). 프로세스가 죽어 남은 rec_* 는 부팅 시 sweep.
프로세스 재시작이면 잡이 사라진다 — 앱은 404 를 받으면 파일이 폰에 있으니 다시 올린다.
"""
import asyncio
import glob
import os
import secrets
import tempfile
import time
from dataclasses import dataclass, field

from fastapi import HTTPException

from app.services import azure_speech_service

JOB_TTL_SEC = 3600          # 결과 보관 1시간 (앱이 가져간 뒤엔 필요 없음)
AZURE_CONCURRENCY = 2
TEMP_PREFIX = "rec_"
_jobs: dict[str, "TranscribeJob"] = {}
_azure_slots = asyncio.Semaphore(AZURE_CONCURRENCY)


@dataclass
class TranscribeJob:
    id: str
    user_id: int
    status: str = "queued"          # queued | running | done | failed
    transcript: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    created: float = field(default_factory=time.monotonic)
    finished: float | None = None
    task: asyncio.Task | None = field(default=None, repr=False)   # strong ref — create_task 결과가 GC 되지 않게


def _sweep() -> None:
    now = time.monotonic()
    for k in [k for k, j in _jobs.items() if j.finished and now - j.finished > JOB_TTL_SEC]:
        _jobs.pop(k, None)


def create(user_id: int) -> TranscribeJob:
    _sweep()
    if any(j.user_id == user_id and j.finished is None for j in _jobs.values()):
        raise HTTPException(status_code=429, detail="A transcription is already running for this account. Wait for it to finish.")
    job = TranscribeJob(id=secrets.token_urlsafe(12), user_id=user_id)
    _jobs[job.id] = job
    return job


def discard(job: TranscribeJob) -> None:
    """파일 수신 단계에서 실패한 잡 슬롯 반납 (사용자당 1건 제한이 막히지 않게)."""
    _jobs.pop(job.id, None)


def get(job_id: str, user_id: int) -> TranscribeJob | None:
    job = _jobs.get(job_id)
    return job if job and job.user_id == user_id else None


def start(job: TranscribeJob, tmp_path: str, filename: str, content_type: str, locale: str, diarize: bool, max_speakers: int) -> None:
    """요청 컨텍스트 밖에서 도는 독립 태스크로 변환을 시작한다 (BackgroundTasks 금지 — 모듈 docstring)."""
    job.task = asyncio.create_task(_run(job, tmp_path, filename, content_type, locale, diarize, max_speakers))


async def _run(job: TranscribeJob, tmp_path: str, filename: str, content_type: str, locale: str, diarize: bool, max_speakers: int) -> None:
    try:
        async with _azure_slots:
            job.status = "running"
            result = await azure_speech_service.transcribe_file(tmp_path, filename, content_type, locale, diarize, max_speakers)
        if not result["transcript"].strip():
            # Azure 가 아무 문장도 못 찾음(무음·잡음) — done+빈 텍스트로 주면 앱이 저장 단계에서 422 를 맞는다 → 명시적으로 실패
            job.status = "failed"
            job.error = "No speech detected in the recording."
        else:
            job.transcript = result["transcript"]
            job.duration_ms = result["duration_ms"]
            job.status = "done"
        print(f"[transcribe] job {job.id} {job.status}: {result['phrases_count']} phrases, audio {result['duration_ms']} ms, azure {result['azure_ms']} ms")
    except Exception as e:  # noqa: BLE001 — 실패 사유를 앱에 그대로 보여준다(키 없음)
        job.status = "failed"
        job.error = str(e)[:300]
        print(f"[transcribe] job {job.id} failed: {job.error}")
    finally:
        job.finished = time.monotonic()
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def sweep_temp_files() -> int:
    """부팅 시: 이전 프로세스가 죽으면서 남긴 rec_* 임시 음성 파일 삭제 (서버에 음성을 남기지 않는다)."""
    n = 0
    for p in glob.glob(os.path.join(tempfile.gettempdir(), f"{TEMP_PREFIX}*")):
        try:
            os.remove(p)
            n += 1
        except OSError:
            pass
    return n
