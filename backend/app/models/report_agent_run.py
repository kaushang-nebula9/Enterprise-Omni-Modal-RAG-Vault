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
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.generated_report import GeneratedReport


class ReportAgentRun(Base):
    __tablename__ = "report_agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("generated_reports.id", ondelete="CASCADE"), nullable=False
    )
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "step_name IN ('gather', 'cluster', 'synthesize', 'assemble', 'render', 'deliver')",
            name="chk_step_name",
        ),
        CheckConstraint(
            "status IN ('running', 'success', 'failed')",
            name="chk_run_status",
        ),
        Index("idx_report_runs_report", "report_id"),
    )

    # Relationships
    report: Mapped["GeneratedReport"] = relationship(
        "GeneratedReport", back_populates="runs"
    )
