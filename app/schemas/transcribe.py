from pydantic import BaseModel


class TranscribeJobOut(BaseModel):
    job_id: str
    status: str                      # queued | running | done | failed
    transcript: str | None = None    # done 일 때. LMS 사이트 형식(줄바꿈, conversation 은 'Guest-n: ')
    duration_ms: int | None = None   # Azure 가 잰 오디오 길이
    error: str | None = None         # failed 일 때
