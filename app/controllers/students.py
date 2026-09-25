from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.student import StudentSearchItem
from app.services import student_service

# 읽기 전용 — 학생 데이터는 LMS 소유. 앱 녹음 화면에서 "누구와의 녹음인지" 고를 때만 쓴다.
router = APIRouter(tags=["Students"])


@router.get("/search", response_model=list[StudentSearchItem])
async def search_students(
    q: str = Query(..., min_length=2, max_length=50, description="이름 부분 일치 (2자 이상)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """이름으로 학생 검색 — 최대 15건, 전 지점. 응답: sid / name / branch(등록 지점) / grade(등록 학년)."""
    return await student_service.search_students(db, q)
