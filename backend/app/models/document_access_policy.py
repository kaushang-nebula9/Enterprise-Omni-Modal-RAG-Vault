from datetime import datetime
import uuid
from sqlalchemy import DateTime, Uuid, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.role import Role
    from app.models.department import Department


class DocumentAccessPolicy(Base):
    __tablename__ = "document_access_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    granted_via: Mapped[str] = mapped_column(
        String, nullable=False, server_default="direct"
    )
    inherited_from_role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("roles.id", ondelete="CASCADE"), nullable=True
    )
    granted_via_department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("departments.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Unique Constraint
    __table_args__ = (
        UniqueConstraint("document_id", "role_id", name="uq_document_id_role_id"),
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document", back_populates="access_policies"
    )
    role: Mapped["Role"] = relationship("Role", foreign_keys=[role_id])
    inherited_from_role: Mapped[Optional["Role"]] = relationship(
        "Role", foreign_keys=[inherited_from_role_id]
    )
    granted_via_department: Mapped[Optional["Department"]] = relationship(
        "Department", foreign_keys=[granted_via_department_id]
    )
