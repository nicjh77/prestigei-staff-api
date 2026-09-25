from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.student import StudentMain
from app.schemas.student import StudentSearchItem

SEARCH_LIMIT = 15


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_students(db: AsyncSession, q: str) -> list[StudentSearchItem]:
    """이름 부분 일치 검색 (앱 녹음 화면의 학생 선택용).

    - 전 지점 대상 (상담은 지점을 넘나들 수 있음). 지점명은 표시용으로만 붙인다.
    - fullname / fname / lname 어디든 포함되면 매치. LIKE 와일드카드는 이스케이프.
    - 앞에서부터 일치하는 이름을 먼저, 그다음 이름순. 최대 15건.
    """
    term = q.strip()
    if len(term) < 2:
        return []
    pat = f"%{_escape_like(term)}%"
    stmt = (
        select(StudentMain, Branch.fullname)
        .outerjoin(Branch, Branch.bid == StudentMain.regbid)
        .where(
            StudentMain.fullname.like(pat, escape="\\")
            | StudentMain.fname.like(pat, escape="\\")
            | StudentMain.lname.like(pat, escape="\\")
        )
        .order_by(
            StudentMain.fullname.like(f"{_escape_like(term)}%", escape="\\").desc(),
            StudentMain.fullname,
            StudentMain.sid.desc(),
        )
        .limit(SEARCH_LIMIT)
    )
    result = await db.execute(stmt)
    items: list[StudentSearchItem] = []
    for student, branch_name in result.all():
        name = (student.fullname or f"{student.fname or ''} {student.lname or ''}").strip()
        if not name:
            continue
        items.append(StudentSearchItem(sid=student.sid, name=name, branch=branch_name, grade=student.entgrade))
    return items
