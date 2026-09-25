from pydantic import BaseModel, Field, field_validator


class TranscriptSaveIn(BaseModel):
    """앱이 Azure 변환 결과를 LMS 테이블에 저장해 달라고 보내는 본문."""
    model_config = {"extra": "forbid"}

    client_id: str = Field(min_length=6, max_length=64)      # 앱 RecordingItem.id — 같은 녹음 재전송 시 중복 저장 방지
    type: str = Field(pattern="^(counseling|tutoring|class)$")
    transcript: str = Field(min_length=1, max_length=2_000_000)
    started_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$")   # 폰 로컬 시각
    student_name: str | None = Field(default=None, max_length=255)
    scid: int | None = None          # tutoring
    cid: int | None = None           # class
    cdid: int | None = None
    ctid: int | None = None          # 없으면 0 으로 저장 (웹과 동일)

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
    action: str         # inserted | appended | duplicate
    sessionid: str | None = None
