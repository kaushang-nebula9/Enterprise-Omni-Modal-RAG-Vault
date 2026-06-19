from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Any
from app.schemas.auth import RoleResponse
from app.models.enums import DocumentStatus, FileType, OwnerType, Visibility


class DocumentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    uploaded_by: UUID
    filename: str
    file_type: FileType
    owner_type: OwnerType
    visibility: Visibility
    chunk_count: int
    qdrant_collection: str
    status: DocumentStatus
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    description: Optional[str] = None
    uploaded_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentWithAccessResponse(DocumentResponse):
    """
    Extends DocumentResponse with a list of RoleResponse objects derived
    from the document's access_policies relationship (policy.role).
    """
    access_policies: list[RoleResponse] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_roles_from_policies(cls, data: Any) -> Any:
        """
        When building from a SQLAlchemy ORM object, convert each
        DocumentAccessPolicy into its nested role (a Role ORM object),
        which Pydantic will then serialise as RoleResponse.
        """
        if hasattr(data, "access_policies"):
            policies = data.access_policies or []
            # Replace the raw policy list with the role objects so Pydantic
            # can serialise them using RoleResponse(from_attributes=True)
            object.__setattr__(
                data,
                "_resolved_roles",
                [p.role for p in policies if p.role is not None],
            )
            # We override access_policies with the resolved roles
            data.__dict__["access_policies"] = [p.role for p in policies if p.role is not None]
        return data


class UpdateDocumentAccessRequest(BaseModel):
    role_ids: list[UUID] = Field(..., min_length=1)
