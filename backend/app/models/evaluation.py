from datetime import datetime
import uuid
from sqlalchemy import Text, DateTime, Uuid, ForeignKey, Integer, Float, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.enums import EvaluationStatus, evaluation_status_enum
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.query_log import QueryLog


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[EvaluationStatus] = mapped_column(
        evaluation_status_enum, default=EvaluationStatus.pending, nullable=False
    )
    query_count: Mapped[int] = mapped_column(Integer, nullable=False)
    date_range_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    date_range_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    avg_faithfulness_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    avg_relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    requested_by_user: Mapped["User"] = relationship("User")
    results: Mapped[List["EvaluationResult"]] = relationship(
        "EvaluationResult",
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    query_log_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("query_logs.id", ondelete="CASCADE"), nullable=False
    )
    faithfulness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    unsupported_claims: Mapped[List[str]] = mapped_column(JSONB, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    evaluation_run: Mapped["EvaluationRun"] = relationship(
        "EvaluationRun", back_populates="results"
    )
    query_log: Mapped["QueryLog"] = relationship("QueryLog")
