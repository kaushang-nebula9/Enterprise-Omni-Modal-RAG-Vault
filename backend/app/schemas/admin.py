from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from typing import Optional
from datetime import date, datetime


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
    default_model_id: Optional[UUID] = None


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    website: str | None = None
    monthly_budget_limit: Optional[float] = None
    default_model_id: Optional[UUID] = None
    estimated_usage_this_month: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelCreateRequest(BaseModel):
    display_name: str = Field(..., min_length=1)
    is_active: bool = True
    provider_id: str = Field(..., min_length=1)
    base_url: Optional[str] = None
    input_cost_per_million_tokens: Optional[float] = None
    output_cost_per_million_tokens: Optional[float] = None
    model_name: str = Field(..., min_length=1)
    api_key: Optional[str] = ""
    is_default: bool = False
    tier: str = Field("balanced", description="Model tier")


class ModelUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None
    provider_id: Optional[str] = None
    base_url: Optional[str] = None
    input_cost_per_million_tokens: Optional[float] = None
    output_cost_per_million_tokens: Optional[float] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    is_default: Optional[bool] = None
    tier: Optional[str] = None


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
    openrouter_llama_input_tokens: int = 0
    openrouter_llama_output_tokens: int = 0
    openrouter_gemma_input_tokens: int = 0
    openrouter_gemma_output_tokens: int = 0
    openrouter_nemotron_input_tokens: int = 0
    openrouter_nemotron_output_tokens: int = 0
    openrouter_gpt_input_tokens: int = 0
    openrouter_gpt_output_tokens: int = 0
    openrouter_cohere_input_tokens: int = 0
    openrouter_cohere_output_tokens: int = 0


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
