import asyncio
import json
import logging
from fastapi import APIRouter, Depends, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse
from app.services.notification_service import register_connection, unregister_connection

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("", response_model=list[NotificationResponse])
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's notifications, most recent first, limit to 50.
    """
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return notifications

@router.patch("/mark-read", response_model=dict)
def mark_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark all unread notifications of the requesting user as read.
    """
    unread_notifs = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)
        .all()
    )
    for notif in unread_notifs:
        notif.is_read = True
    db.commit()
    return {"message": "All notifications marked as read"}

@router.get("/stream")
async def stream_notifications(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    SSE endpoint to keep connection open per user, push new notifications in real time.
    """
    queue = register_connection(current_user.id)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(payload)}\n\n"
                    queue.task_done()
                except asyncio.TimeoutError:
                    # Keep-alive comment
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unregister_connection(current_user.id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
