"""변환 잡 (in-memory, 단일 프로세스). 앱: POST 파일 → job_id 즉시 → GET 으로 폴링.

요청 안에서 Azure 를 기다리면 Apache 프록시 유휴 타임아웃(기본 60초)에 걸리므로 백그라운드로 뺀다.
프로세스 재시작이면 잡이 사라진다 — 앱은 'failed/unknown' 을 받으면 파일이 폰에 있으니 다시 올리면 된다.
임시 파일은 Azure 호출이 끝나는 즉시 삭제 (서버에 음성을 남기지 않는다는 원칙).
"""
import asyncio
import os
import secrets
import time
from dataclasses import dataclass, field

from app.services import azure_speech_service

JOB_TTL_SEC = 3600          # 결과 보관 1시간 (앱이 가져간 뒤엔 필요 없음)
_jobs: dict[str, "TranscribeJob"] = {}


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


def _sweep() -> None:
    now = time.monotonic()
    for k in [k for k, j in _jobs.items() if j.finished and now - j.finished > JOB_TTL_SEC]:
        _jobs.pop(k, None)


def create(user_id: int) -> TranscribeJob:
    _sweep()
    job = TranscribeJob(id=secrets.token_urlsafe(12), user_id=user_id)
    _jobs[job.id] = job
    return job


def get(job_id: str, user_id: int) -> TranscribeJob | None:
    job = _jobs.get(job_id)
    return job if job and job.user_id == user_id else None


async def run(job: TranscribeJob, tmp_path: str, filename: str, content_type: str, locale: str, diarize: bool, max_speakers: int = 2) -> None:
    job.status = "running"
    try:
        result = await azure_speech_service.transcribe_file(tmp_path, filename, content_type, locale, diarize, max_speakers)
        job.transcript = result["transcript"]
        job.duration_ms = result["duration_ms"]
        job.status = "done"
        print(f"[transcribe] job {job.id} done: {result['phrases_count']} phrases, audio {result['duration_ms']} ms, azure {result['azure_ms']} ms")
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
        await asyncio.sleep(0)
