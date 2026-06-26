from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from datetime import datetime
from typing import Optional

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
    monthly_budget_limit: Optional[float] = None

class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    website: str | None = None
    monthly_budget_limit: Optional[float] = None
    estimated_usage_this_month: Optional[float] = None
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
    input_price_per_million: Optional[float] = None
    output_price_per_million: Optional[float] = None

class ModelUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1)
    provider: Optional[ModelProvider] = None
    model_string: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None
    input_price_per_million: Optional[float] = None
    output_price_per_million: Optional[float] = None

from datetime import date, datetime
from uuid import UUID

class UsageSummaryItem(BaseModel):
    date: date
    request_count: int
    total_tokens: int
    claude_input_tokens: int
    claude_output_tokens: int
    openrouter_input_tokens: int
    openrouter_output_tokens: int
    claude_haiku_input_tokens: int
    claude_haiku_output_tokens: int
    claude_sonnet_input_tokens: int
    claude_sonnet_output_tokens: int
    claude_opus_input_tokens: int
    claude_opus_output_tokens: int

class UsageSummaryResponse(BaseModel):
    usage: list[UsageSummaryItem]

class DashboardOverviewResponse(BaseModel):
    department_count: int
    document_count: int
    role_count: int
    member_count: int

class DocumentTypeCount(BaseModel):
    file_type: str
    count: int

class RecentDocumentItem(BaseModel):
    filename: str
    file_type: str
    uploaded_by: str
    uploaded_at: datetime
    status: str

class DocumentInsightsResponse(BaseModel):
    distribution: list[DocumentTypeCount]
    recent_documents: list[RecentDocumentItem]



