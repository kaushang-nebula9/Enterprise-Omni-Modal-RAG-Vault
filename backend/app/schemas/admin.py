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

from app.models.enums import ModelProvider
from typing import Optional

class ModelCreateRequest(BaseModel):
    display_name: str = Field(..., min_length=1)
    provider: ModelProvider
    model_string: str = Field(..., min_length=1)
    is_active: bool = True

class ModelUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1)
    provider: Optional[ModelProvider] = None
    model_string: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None

from datetime import date

class UsageSummaryItem(BaseModel):
    date: date
    request_count: int
    total_tokens: int

class UsageSummaryResponse(BaseModel):
    usage: list[UsageSummaryItem]


