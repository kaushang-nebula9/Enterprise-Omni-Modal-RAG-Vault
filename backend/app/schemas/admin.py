from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from datetime import datetime

class AdminStatsResponse(BaseModel):
    total_documents: int
    total_members: int
    total_roles: int

class UpdateMemberRequest(BaseModel):
    role_id: UUID | None = None
    is_active: bool | None = None

class UpdateOrganisationRequest(BaseModel):
    name: str | None = Field(None, min_length=2)
    website: HttpUrl | None = None

class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    website: str | None = None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
