from datetime import datetime
import uuid
from sqlalchemy import String, Text, DateTime, Uuid, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.external_database import ExternalDatabaseConnection


class DBQueryLog(Base):
    __tablename__ = "db_query_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("external_database_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    natural_language_query: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "success" or "failed"
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # "Ambiguous" | "SQL Error" | "Unauthorized Column" | "Timeout" | "Other"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped["User"] = relationship("User")
    db_connection: Mapped["ExternalDatabaseConnection"] = relationship(
        "ExternalDatabaseConnection"
    )
