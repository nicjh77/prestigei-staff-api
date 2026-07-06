import html as html_lib
import logging
import re
from datetime import datetime, timezone

import anyio
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.database import AsyncSessionLocal
from app.models.notification import NotificationLog, NotificationRecipient, PushToken
from app.models.user import User
from app.schemas.notification import NotificationItem, PushTokenRegister, SendNotificationRequest
from app.utils.expo_push import send_push_notifications


def _strip_html(text: str) -> str:
    """HTML 태그 제거 + 엔티티 디코딩. OS 알림 배너용 plain text 변환에 사용."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_lib.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


async def register_token(db: AsyncSession, user: User, data: PushTokenRegister) -> None:
    result = await db.execute(
        select(PushToken).where(PushToken.user_id == user.id, PushToken.device_id == data.device_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.push_token = data.push_token
        existing.platform = data.platform
        existing.is_active = True
    else:
        db.add(PushToken(user_id=user.id, push_token=data.push_token, device_id=data.device_id, platform=data.platform))


async def deregister_token(db: AsyncSession, user: User, device_id: str) -> None:
    result = await db.execute(
        select(PushToken).where(PushToken.user_id == user.id, PushToken.device_id == device_id)
    )
    token = result.scalar_one_or_none()
    if token:
        token.is_active = False


async def prepare_notification(db: AsyncSession, data: SendNotificationRequest) -> int:
    """알림 로그 + 수신자 레코드를 요청 트랜잭션 안에서 생성하고 log.id 반환.

    실제 Expo 푸시 발송은 이 트랜잭션 밖(백그라운드 `dispatch_notification`)에서
    처리한다 — 외부 HTTP 호출 동안 DB 커넥션을 점유해 풀이 고갈되는 것을 방지.
    """
    log = NotificationLog(
        user_id=None, title=data.title, body=data.body, data=data.data, status="pending"
    )
    db.add(log)
    await db.flush()  # log.id 확보 (recipient 생성에 필요)

    # 대상 user_id 확정 — 항상 t_user에 실제 존재하고 소프트 삭제되지 않은(del_yn='N')
    # id로만 필터링. (LMS가 없는 id를 보내도 FK 위반으로 전체 트랜잭션이 롤백되지 않게 하고,
    #  IN 절이 중복도 자연스럽게 제거해 (notification_id, user_id) unique 위반 방지)
    # user_ids가 None이면 브로드캐스트, 빈 리스트([])면 '대상 없음'(전체 발송 아님)이다.
    base = select(User.id).where(User.del_yn == "N")
    if data.user_ids is not None:
        base = base.where(User.id.in_(data.user_ids))
    result = await db.execute(base)
    target_ids = [row[0] for row in result.all()]

    if target_ids:
        now = datetime.now(timezone.utc)
        await db.execute(
            insert(NotificationRecipient),
            [{"notification_id": log.id, "user_id": uid, "created_at": now, "updated_at": now} for uid in target_ids],
        )

    return log.id


async def dispatch_notification(
    log_id: int,
    user_ids: list[int] | None,
    title: str,
    body: str,
    data: dict | None,
) -> None:
    """백그라운드에서 Expo 푸시를 발송하고 로그 상태를 갱신한다.

    요청 트랜잭션과 분리된 자체 세션을 쓰며, 외부 HTTP 호출(가장 오래 걸리는 구간)
    동안에는 DB 커넥션을 반납한 상태로 대기한다.
    """
    try:
        # 1) 활성 토큰 조회 — 짧은 세션, 조회 후 커넥션 즉시 반납.
        #    소프트 삭제된 사용자(del_yn='Y')의 토큰은 제외. user_ids가 None이면 브로드캐스트.
        async with AsyncSessionLocal() as session:
            query = (
                select(PushToken.push_token)
                .join(User, User.id == PushToken.user_id)
                .where(PushToken.is_active == True, User.del_yn == "N")  # noqa: E712
            )
            if user_ids is not None:
                query = query.where(PushToken.user_id.in_(user_ids))
            tokens = [row[0] for row in (await session.execute(query)).all()]

        # 2) 푸시 발송 — DB 커넥션을 잡지 않은 상태로 외부 HTTP 수행
        invalid_tokens: list[str] = []
        if not tokens:
            status_val = "sent"
            response_val = "no active tokens"
        else:
            try:
                # DB에는 HTML 원본 저장, 배너에는 plain text 전송
                send_result = await anyio.to_thread.run_sync(
                    send_push_notifications, tokens, _strip_html(title), _strip_html(body), data or {}
                )
                invalid_tokens = send_result.invalid_tokens
                status_val = "sent" if send_result.success_count > 0 else "failed"
                response_val = (
                    f"success={send_result.success_count} failure={send_result.failure_count}"
                    + (f" | {send_result.errors[0]}" if send_result.errors else "")
                )
            except Exception as e:
                status_val = "failed"
                response_val = str(e)

        # 3) 로그 상태 갱신 + Expo가 DeviceNotRegistered로 보고한 죽은 토큰 비활성화
        #    (짧은 세션 — 백그라운드 태스크라 get_db가 없으므로 명시적으로 커밋)
        async with AsyncSessionLocal() as session:
            values: dict = {"status": status_val, "push_response": response_val[:500]}
            if status_val == "sent":
                values["sent_at"] = datetime.now(timezone.utc)
            await session.execute(
                update(NotificationLog).where(NotificationLog.id == log_id).values(**values)
            )
            if invalid_tokens:
                await session.execute(
                    update(PushToken).where(PushToken.push_token.in_(invalid_tokens)).values(is_active=False)
                )
            await session.commit()
    except Exception:
        # 백그라운드 태스크 예외는 응답 이후라 삼켜진다 — DB 조회/갱신 실패로 로그가 'pending'에
        # 영구 방치되지 않도록, 별도 세션에서 best-effort로 'failed' 기록.
        logger.exception("dispatch_notification failed (log_id=%s)", log_id)
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(NotificationLog)
                    .where(NotificationLog.id == log_id)
                    .values(status="failed", push_response="dispatch error")
                )
                await session.commit()
        except Exception:
            logger.exception("failed to mark notification log %s as failed", log_id)


async def get_notifications(db: AsyncSession, user_id: int, page: int, size: int) -> dict:
    """현재 유저의 알림 목록 (페이지네이션)"""
    base = (
        select(NotificationRecipient, NotificationLog)
        .join(NotificationLog, NotificationRecipient.notification_id == NotificationLog.id)
        .where(NotificationRecipient.user_id == user_id)
    )

    # total count
    count_q = select(func.count()).select_from(
        base.with_only_columns(NotificationRecipient.id).subquery()
    )
    total = (await db.execute(count_q)).scalar() or 0

    # unread count
    unread_q = select(func.count()).select_from(
        base.where(NotificationRecipient.is_read == False).with_only_columns(NotificationRecipient.id).subquery()  # noqa: E712
    )
    unread_count = (await db.execute(unread_q)).scalar() or 0

    # items
    rows = await db.execute(
        base.order_by(NotificationRecipient.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )

    items = []
    for recipient, log in rows.all():
        items.append(NotificationItem(
            id=recipient.id,
            notification_id=log.id,
            title=log.title,
            body=log.body,
            data=log.data,
            is_read=bool(recipient.is_read),
            created_at=recipient.created_at,
        ))

    return {"items": items, "total": total, "unread_count": unread_count}


async def get_unread_count(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .where(NotificationRecipient.user_id == user_id, NotificationRecipient.is_read == False)  # noqa: E712
    )
    return result.scalar() or 0


async def mark_as_read(db: AsyncSession, user_id: int, recipient_id: int) -> bool:
    result = await db.execute(
        select(NotificationRecipient)
        .where(NotificationRecipient.id == recipient_id, NotificationRecipient.user_id == user_id)
    )
    recipient = result.scalar_one_or_none()
    if not recipient:
        return False
    recipient.is_read = True
    recipient.read_at = datetime.now(timezone.utc)
    return True


async def mark_all_as_read(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        update(NotificationRecipient)
        .where(NotificationRecipient.user_id == user_id, NotificationRecipient.is_read == False)  # noqa: E712
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    return result.rowcount
