from pydantic import BaseModel


class BranchOut(BaseModel):
    bid: int
    name: str            # t_branch.fullname
    short: str | None    # t_branch.shortname


class RecordingSessionOut(BaseModel):
    """앱 Recording 화면의 일정 선택 항목 — Tutoring / Class 공용 (LMS recording 사이트의 목록과 같은 의미).

    Tutoring: scid 로 식별 (t_tutorschedule). Class: cid + cdid + ctid 로 식별 (t_classdate × t_classteacher, ctid 는 없을 수 있음).
    """
    kind: str                    # tutoring | class
    scid: int | None = None
    cid: int | None = None
    cdid: int | None = None
    ctid: int | None = None
    title: str                   # Tutoring: "[교사별칭]-학생명" / Class: 클래스명
    teacher: str | None
    student: str | None          # Tutoring 만
    branch: str | None           # t_branch.shortname
    bid: int | None
    date: str                    # YYYY-MM-DD
    start_time: str | None       # HH:MM
    end_time: str | None
    attendance: str | None       # Tutoring 만 (Scheduled / Not checked / …)
    memo: str | None
    past: bool
    mine: bool                   # 로그인 사용자(t_user.tid)가 담당 교사인 일정
