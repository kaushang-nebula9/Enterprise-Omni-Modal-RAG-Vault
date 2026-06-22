"""
Pydantic schemas for the Chat / RAG query endpoints.
"""
from pydantic import BaseModel, Field, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Any


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    tenant_id: UUID
    title: Optional[str] = None
    is_pinned: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateSessionResponse(SessionResponse):
    """Alias used for session creation responses (identical fields)."""
    pass


class CitationResponse(BaseModel):
    id: UUID
    document_id: UUID
    filename: str = ""
    chunk_text: str
    page_number: Optional[int] = None
    chunk_index: int

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def resolve_filename(cls, data: Any) -> Any:
        """
        When building from a SQLAlchemy ORM QueryCitation object,
        extract the filename from the related document relationship.
        """
        if hasattr(data, "document") and data.document is not None:
            # Inject filename from the related Document
            data.__dict__["filename"] = data.document.filename
        return data


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    created_at: datetime
    citations: list[CitationResponse] = []
    attached_file: Optional[dict] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def resolve_attached_file(cls, data: Any) -> Any:
        if isinstance(data, dict):
            attached_doc = data.get("attached_document")
            if attached_doc:
                if hasattr(attached_doc, "filename"):
                    data["attached_file"] = {
                        "name": attached_doc.filename,
                        "size": getattr(attached_doc, "file_size", 0) or 0
                    }
                elif isinstance(attached_doc, dict):
                    data["attached_file"] = {
                        "name": attached_doc.get("filename"),
                        "size": attached_doc.get("file_size") or 0
                    }
        else:
            attached_doc = getattr(data, "attached_document", None)
            if attached_doc is not None:
                data.__dict__["attached_file"] = {
                    "name": attached_doc.filename,
                    "size": attached_doc.file_size or 0
                }
        return data


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse] = []


class QueryRequest(BaseModel):
    content: str = Field(..., min_length=1, strip_whitespace=True)
    document_id: Optional[UUID] = None



class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    message_id: str


class TranscriptionResponse(BaseModel):
    text: str
