from datetime import datetime
import uuid
from sqlalchemy import String, DateTime, Uuid, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.role import Role


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Unique constraint on (tenant_id, name)
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tenant_id_department_name"),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    roles: Mapped[list["Role"]] = relationship("Role", back_populates="department")
