from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class CreateDepartmentRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)


class UpdateDepartmentRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)


class DepartmentResponse(BaseModel):
    id: UUID
    name: str
    tenant_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
