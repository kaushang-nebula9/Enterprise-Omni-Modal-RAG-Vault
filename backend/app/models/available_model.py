from datetime import datetime
import uuid
from sqlalchemy import String, DateTime, Boolean, Uuid, func, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from typing import Optional
from decimal import Decimal


class AvailableModel(Base):
    __tablename__ = "available_models"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # New provider registry fields
    provider_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    input_cost_per_million_tokens: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    output_cost_per_million_tokens: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )

    # Tenant scoping fields
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True
    )
    api_key: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, default=""
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
