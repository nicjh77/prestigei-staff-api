from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.bulletin import BulletinPost
from app.models.user import User
from app.schemas.notice import NoticeDetail, NoticeListItem

# t_noticeboard.bid: '%' = 전체 공지, 그 외에는 지점 id 문자열('4' 등).
# t_noticeboard.wid = t_user.id (작성자). branch 라벨은 USP_SELNOTICEBOARD/DETAIL 규칙을 따른다.
_BRANCH_LABEL = case((BulletinPost.bid == "%", "ALL"), else_=Branch.fullname)


def _allowed_bids(user: User) -> list[str]:
    """사용자에게 보이는 공지 대상 — 전체('%') + 소속 지점."""
    bids = ["%"]
    if user.bid is not None:
        bids.append(str(user.bid))
    return bids


async def list_notices(
    db: AsyncSession, user: User, page: int, size: int
) -> tuple[list[NoticeListItem], int]:
    base = (
        select(
            BulletinPost.id,
            BulletinPost.title,
            BulletinPost.regdate,
            _BRANCH_LABEL.label("branch"),
        )
        .outerjoin(Branch, Branch.bid == BulletinPost.bid)
        .where(BulletinPost.delyn == "N", BulletinPost.bid.in_(_allowed_bids(user)))
        .order_by(BulletinPost.regdate.desc())
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * size).limit(size))).all()
    items = [
        NoticeListItem(
            id=r.id,
            title=r.title,
            regdate=r.regdate.strftime("%Y-%m-%d") if r.regdate else None,
            branch=r.branch or "-",
        )
        for r in rows
    ]
    return items, total


async def get_notice(db: AsyncSession, notice_id: int, user: User) -> NoticeDetail:
    stmt = (
        select(
            BulletinPost.id,
            BulletinPost.title,
            BulletinPost.regdate,
            BulletinPost.details,
            _BRANCH_LABEL.label("branch"),
            User.loginid.label("noticed_by"),
        )
        .outerjoin(Branch, Branch.bid == BulletinPost.bid)
        .outerjoin(User, User.id == BulletinPost.wid)
        .where(
            BulletinPost.id == notice_id,
            BulletinPost.delyn == "N",
            BulletinPost.bid.in_(_allowed_bids(user)),  # 다른 지점 공지 id 직접 조회(IDOR) 차단
        )
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")
    return NoticeDetail(
        id=row.id,
        title=row.title,
        regdate=row.regdate.strftime("%Y-%m-%d") if row.regdate else None,
        branch=row.branch or "-",
        details=row.details,
        noticed_by=row.noticed_by.upper() if row.noticed_by else None,
    )
