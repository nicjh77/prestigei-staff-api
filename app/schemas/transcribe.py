from pydantic import BaseModel

from app.schemas.transcript import TranscriptSaveOut


class TranscribeJobOut(BaseModel):
    job_id: str
    status: str                      # queued | running | done | failed
    transcript: str | None = None    # done 일 때. LMS 사이트 형식(줄바꿈, conversation 은 'Guest-n: ')
    duration_ms: int | None = None   # Azure 가 잰 오디오 길이
    error: str | None = None         # failed 일 때
    saved: TranscriptSaveOut | None = None   # 서버가 LMS 테이블에 저장한 결과 (2026-09-28: 변환 직후 서버가 직접 저장)
