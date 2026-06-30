from datetime import datetime
import uuid
from sqlalchemy import String, DateTime, Uuid, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.enums import NotificationType, notification_type_enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.tenant import Tenant
    from app.models.document import Document
    from app.models.role import Role
    from app.models.department import Department
    from app.models.evaluation import EvaluationRun


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[NotificationType] = mapped_column(
        notification_type_enum, nullable=False
    )
    message: Mapped[str] = mapped_column(String, nullable=False)
    related_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    related_role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    related_department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    related_evaluation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=datetime.now,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    tenant: Mapped["Tenant"] = relationship("Tenant")
    related_document: Mapped[Optional["Document"]] = relationship("Document")
    related_role: Mapped[Optional["Role"]] = relationship("Role")
    related_department: Mapped[Optional["Department"]] = relationship("Department")
    related_evaluation: Mapped[Optional["EvaluationRun"]] = relationship(
        "EvaluationRun"
    )
