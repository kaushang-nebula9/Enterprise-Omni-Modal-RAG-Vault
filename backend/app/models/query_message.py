from datetime import datetime
import uuid
from sqlalchemy import Text, DateTime, Uuid, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.enums import message_role_enum, MessageRole

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.query_citation import QueryCitation
    from app.models.query_session import QuerySession
    from app.models.document import Document
    

class QueryMessage(Base):
    __tablename__ = "query_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, 
        ForeignKey("query_sessions.id", ondelete="CASCADE"), 
        nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(message_role_enum, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    attached_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    session: Mapped["QuerySession"] = relationship("QuerySession", back_populates="messages")
    citations: Mapped[list["QueryCitation"]] = relationship("QueryCitation", back_populates="message", cascade="all, delete-orphan")
    attached_document: Mapped[Optional["Document"]] = relationship("Document")


