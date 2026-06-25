from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models.enums import NotificationType

class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    tenant_id: UUID
    type: NotificationType
    message: str
    related_document_id: Optional[UUID] = None
    related_role_id: Optional[UUID] = None
    related_department_id: Optional[UUID] = None
    is_read: bool
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
