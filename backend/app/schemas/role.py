from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional
from app.schemas.auth import RoleResponse

class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    parent_role_id: Optional[UUID] = None

class UpdateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    parent_role_id: Optional[UUID] = None

__all__ = ["CreateRoleRequest", "UpdateRoleRequest", "RoleResponse"]

