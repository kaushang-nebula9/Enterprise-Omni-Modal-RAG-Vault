from datetime import datetime
import uuid
from sqlalchemy import String, DateTime, Uuid, func, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User
    from app.models.query_session import QuerySession
    from app.models.role import Role
    from app.models.available_model import AvailableModel


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    monthly_budget_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    default_model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("available_models.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="tenant", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="tenant", cascade="all, delete-orphan"
    )
    query_sessions: Mapped[list["QuerySession"]] = relationship(
        "QuerySession", back_populates="tenant", cascade="all, delete-orphan"
    )
    roles: Mapped[list["Role"]] = relationship(
        "Role", back_populates="tenant", cascade="all, delete-orphan"
    )
    default_model: Mapped[Optional["AvailableModel"]] = relationship(
        "AvailableModel", foreign_keys=[default_model_id]
    )
