from datetime import datetime
import uuid
from sqlalchemy import String, DateTime, Boolean, Uuid, func, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.enums import model_provider_enum, ModelProvider
from typing import Optional
from decimal import Decimal

class AvailableModel(Base):
    __tablename__ = "available_models"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[ModelProvider] = mapped_column(model_provider_enum, nullable=False)
    model_string: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    input_price_per_million: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    output_price_per_million: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
