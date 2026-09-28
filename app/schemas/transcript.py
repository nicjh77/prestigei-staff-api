from pydantic import BaseModel, Field, field_validator


class TranscriptMeta(BaseModel):
    """녹음 1건의 저장 메타 — POST /recordings/transcribe 가 파일과 함께 받는다 (서버가 변환 후 직접 LMS 에 저장)."""
    model_config = {"extra": "forbid"}

    client_id: str = Field(min_length=6, max_length=64)      # 앱 RecordingItem.id — 같은 녹음 재전송 시 중복 저장 방지
    type: str = Field(pattern="^(counseling|tutoring|class)$")
    started_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$")   # 폰 로컬 시각
    student_name: str | None = Field(default=None, max_length=255)
    scid: int | None = None          # tutoring
    cid: int | None = None           # class
    cdid: int | None = None
    ctid: int | None = None          # 없으면 0 으로 저장 (웹과 동일)
    save_mode: str = Field(default="append", pattern="^(append|replace)$")
    # tutoring/class 에 기존 녹취가 있을 때: append(기본) = 뒤에 이어붙임 / replace = 기존 텍스트를 지우고 새 텍스트로 (앱이 일정 선택 시
    # 사용자에게 물어 정함, 2026-09-28). 제출(submitdate)된 행은 둘 다 409. counseling 은 매번 새 행이라 무시. 구 앱은 안 보냄 → append.


class TranscriptSaveIn(TranscriptMeta):
    """(구) 앱이 변환 텍스트를 직접 보내 저장하는 본문 — 2026-09-28 부터 서버가 저장하므로 예비용."""
    transcript: str = Field(min_length=1, max_length=2_000_000)

    @field_validator("transcript")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("transcript is empty")
        return v


class TranscriptSaveOut(BaseModel):
    table: str          # t_tutor_record | t_class_record | t_meeting_record
    id: int
    action: str         # inserted | appended | replaced | duplicate
    sessionid: str | None = None
