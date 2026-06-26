from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.models.enums import EvaluationStatus

class EvaluationRunRequest(BaseModel):
    query_count: Optional[int] = Field(default=None, description="Number of latest queries to evaluate")
    date_range_start: Optional[datetime] = Field(default=None, description="Start range for filtering query logs")
    date_range_end: Optional[datetime] = Field(default=None, description="End range for filtering query logs")

class EvaluationRunResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    requested_by_user_id: UUID
    status: EvaluationStatus
    query_count: int
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    avg_faithfulness_score: Optional[float] = None
    avg_relevance_score: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

class EvaluationResultResponse(BaseModel):
    id: UUID
    evaluation_run_id: UUID
    query_log_id: UUID
    faithfulness_score: int
    relevance_score: int
    unsupported_claims: List[str]
    reasoning: str
    created_at: datetime
    question: Optional[str] = None
    answer: Optional[str] = None

    model_config = {
        "from_attributes": True
    }

class EvaluationDetailResponse(BaseModel):
    run: EvaluationRunResponse
    results: List[EvaluationResultResponse]
