from pydantic import BaseModel


class StudentSearchItem(BaseModel):
    sid: int
    name: str
    branch: str | None      # 등록 지점 라벨 (t_branch.fullname)
    grade: int | None       # 등록 시 학년 (entgrade)
