from datetime import datetime
import uuid
from sqlalchemy import (
    String,
    DateTime,
    Uuid,
    ForeignKey,
    func,
    Text,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.query_session import QuerySession
    from app.models.user import User
    from app.models.report_agent_run import ReportAgentRun


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("query_sessions.id", ondelete="CASCADE"), nullable=False
    )
    generated_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="generating", default="generating"
    )
    storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('generating', 'complete', 'failed')",
            name="chk_report_status",
        ),
        Index("idx_reports_session", "session_id"),
        Index("idx_reports_tenant", "tenant_id"),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    session: Mapped["QuerySession"] = relationship("QuerySession")
    user: Mapped["User"] = relationship("User")
    runs: Mapped[List["ReportAgentRun"]] = relationship(
        "ReportAgentRun",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportAgentRun.created_at.asc()",
    )
