import asyncio
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[NotificationResponse])
def get_notifications(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
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
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Mark all unread notifications of the requesting user as read.
    """
    unread_notifs = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id, Notification.is_read.is_(False)
        )
        .all()
    )
    for notif in unread_notifs:
        notif.is_read = True
    db.commit()
    return {"message": "All notifications marked as read"}


@router.get("/stream")
async def stream_notifications(
    request: Request, current_user: User = Depends(get_current_user)
):
    """
    SSE endpoint to keep connection open per user, push new notifications in real time.
    """

    async def event_generator():
        client = aioredis.from_url(settings.REDIS_URL)
        pubsub = client.pubsub()
        await pubsub.subscribe(f"notifications:{current_user.id}")
        logger.info(f"User {current_user.id} subscribed to Redis notifications stream")

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=15.0
                    )
                    if message:
                        data_str = message["data"]
                        if isinstance(data_str, bytes):
                            data_str = data_str.decode("utf-8")
                        yield f"data: {data_str}\n\n"
                    else:
                        yield ": keepalive\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except Exception as e:
                    logger.error(f"Error in SSE stream for user {current_user.id}: {e}")
                    await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await pubsub.unsubscribe(f"notifications:{current_user.id}")
                await pubsub.aclose()
                await client.aclose()
                logger.info(
                    f"User {current_user.id} unsubscribed and closed Redis stream connection"
                )
            except Exception as e:
                logger.error(
                    f"Error during clean up of Redis SSE stream for user {current_user.id}: {e}"
                )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
