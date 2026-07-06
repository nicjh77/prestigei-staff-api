from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin_or_api_key
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.notification import (
    NotificationListResponse,
    PushTokenRegister,
    SendNotificationRequest,
    UnreadCountResponse,
)
from app.services import notification_service

router = APIRouter(tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.get_notifications(db, current_user.id, page, size)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = await notification_service.get_unread_count(db, current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.patch("/{recipient_id}/read", response_model=MessageResponse)
async def mark_read(recipient_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    ok = await notification_service.mark_as_read(db, current_user.id, recipient_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return MessageResponse(message="Marked as read")


@router.patch("/read-all", response_model=MessageResponse)
async def mark_all_read(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = await notification_service.mark_all_as_read(db, current_user.id)
    return MessageResponse(message=f"{count} notifications marked as read")


@router.post("/token", response_model=MessageResponse)
async def register_token(data: PushTokenRegister, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await notification_service.register_token(db, current_user, data)
    return MessageResponse(message="Token registered")


@router.delete("/token", response_model=MessageResponse)
async def deregister_token(device_id: str = Query(...), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await notification_service.deregister_token(db, current_user, device_id)
    return MessageResponse(message="Token deregistered")


@router.post("/send", response_model=MessageResponse)
async def send_notification(
    data: SendNotificationRequest,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_admin_or_api_key),
    db: AsyncSession = Depends(get_db),
):
    # 로그 + 수신자 레코드는 요청 트랜잭션에서 즉시 기록(커밋)하고,
    # 실제 Expo 발송은 응답 이후 백그라운드에서 처리 → DB 커넥션을 오래 점유하지 않음
    log_id = await notification_service.prepare_notification(db, data)
    background_tasks.add_task(
        notification_service.dispatch_notification,
        log_id, data.user_ids, data.title, data.body, data.data,
    )
    return MessageResponse(message="Notification sent")
