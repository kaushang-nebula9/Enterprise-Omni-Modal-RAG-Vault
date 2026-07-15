from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# Request schemas
class CollectionCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be empty or only whitespace")
        return stripped


class CollectionRename(BaseModel):
    name: str = Field(..., max_length=100)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be empty or only whitespace")
        return stripped


class DocumentMoveToCollection(BaseModel):
    collection_id: Optional[UUID] = (
        None  # null means remove from collection (uncategorize)
    )


# Response schemas
class CollectionResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    created_by: UUID  # user id
    created_at: datetime
    updated_at: datetime
    document_count: int  # count of documents in this collection

    model_config = {"from_attributes": True}


class CollectionListResponse(BaseModel):
    collections: List[CollectionResponse]
    uncategorized_count: (
        int  # count of documents with collection_id = null for this tenant
    )
    total_documents: int  # total documents across all collections + uncategorized
