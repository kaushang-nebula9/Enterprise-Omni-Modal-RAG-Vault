from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Any


class AuditLogItemResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    actor_user_id: UUID
    actor_name: str
    action: str
    description: str
    metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItemResponse]
    total: int
    limit: int
    offset: int
