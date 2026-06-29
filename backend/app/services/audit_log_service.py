from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
import uuid
from typing import Any

def log_audit_event(
    db: Session,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    action: str,
    description: str,
    metadata: dict[str, Any] | None = None
) -> AuditLog:
    """
    Synchronously inserts an audit log event into the database.
    This is a plain synchronous insert with no background tasks, SSE, or side effects.
    """
    db_log = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        description=description,
        metadata_=metadata
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log
