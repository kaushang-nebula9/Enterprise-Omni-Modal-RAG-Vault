from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional
from app.schemas.auth import RoleResponse


class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    parent_role_id: Optional[UUID] = None
    department_id: Optional[UUID] = None


class UpdateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    parent_role_id: Optional[UUID] = None
    department_id: Optional[UUID] = None


class RoleTreeNode(BaseModel):
    """A single role node in the hierarchy tree response."""

    id: UUID
    name: str
    parent_role_id: Optional[UUID] = None
    is_admin: bool = False
    is_default: bool = False
    descendant_count: int
    children: list["RoleTreeNode"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# Resolve forward reference for the recursive children field
RoleTreeNode.model_rebuild()

__all__ = ["CreateRoleRequest", "UpdateRoleRequest", "RoleResponse", "RoleTreeNode"]
