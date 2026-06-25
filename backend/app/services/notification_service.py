import asyncio
import uuid
from typing import Optional
import logging
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.enums import NotificationType

logger = logging.getLogger(__name__)

# Map user_id to a list of active connection queues
active_connections: dict[uuid.UUID, list[asyncio.Queue]] = {}

def register_connection(user_id: uuid.UUID) -> asyncio.Queue:
    queue = asyncio.Queue()
    if user_id not in active_connections:
        active_connections[user_id] = []
    active_connections[user_id].append(queue)
    logger.info(f"Registered SSE connection for user {user_id}. Active connections: {len(active_connections[user_id])}")
    return queue

def unregister_connection(user_id: uuid.UUID, queue: asyncio.Queue):
    if user_id in active_connections:
        if queue in active_connections[user_id]:
            active_connections[user_id].remove(queue)
        if not active_connections[user_id]:
            del active_connections[user_id]
    logger.info(f"Unregistered SSE connection for user {user_id}")

def create_notification(
    db: Session,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    type: NotificationType,
    message: str,
    related_document_id: Optional[uuid.UUID] = None,
    related_role_id: Optional[uuid.UUID] = None,
    related_department_id: Optional[uuid.UUID] = None,
    flush_only: bool = False,
) -> Notification:
    """
    Inserts a notification into the DB and pushes it to active SSE queues for user_id.

    When flush_only=True the function only flushes the row within the current
    session instead of committing.  Use this when calling from inside a larger
    transaction that will be committed by the caller (e.g. during document upload).
    The SSE push is deferred until after the caller commits in that case.
    """
    # Create DB entry
    notification = Notification(
        user_id=user_id,
        tenant_id=tenant_id,
        type=type,
        message=message,
        related_document_id=related_document_id,
        related_role_id=related_role_id,
        related_department_id=related_department_id,
        is_read=False,
    )
    db.add(notification)

    if flush_only:
        # Caller owns the transaction — just flush so the row gets an id
        # without ending the transaction.  The caller must commit afterwards.
        db.flush()
    else:
        db.commit()
        db.refresh(notification)

    # Construct notification payload
    payload = {
        "id": str(notification.id),
        "user_id": str(notification.user_id),
        "tenant_id": str(notification.tenant_id),
        "type": notification.type.value,
        "message": notification.message,
        "related_document_id": str(notification.related_document_id) if notification.related_document_id else None,
        "related_role_id": str(notification.related_role_id) if notification.related_role_id else None,
        "related_department_id": str(notification.related_department_id) if notification.related_department_id else None,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }

    # Push to active SSE connections if they exist
    if user_id in active_connections:
        logger.info(f"Pushing notification {notification.id} to {len(active_connections[user_id])} active SSE streams for user {user_id}")
        for queue in active_connections[user_id]:
            queue.put_nowait(payload)

    return notification
