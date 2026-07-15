from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class ReportCreateResponse(BaseModel):
    report_id: UUID
    status: str

    model_config = {"from_attributes": True}


class ReportStepResponse(BaseModel):
    step_name: str
    status: str
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class ReportStatusResponse(BaseModel):
    report_id: UUID
    session_id: UUID
    session_title: Optional[str] = None
    source_type: str
    sources_used: list[str]
    status: str
    title: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    steps: list[ReportStepResponse]

    model_config = {"from_attributes": True}
