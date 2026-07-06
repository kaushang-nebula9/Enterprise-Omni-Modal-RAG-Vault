from datetime import datetime
import uuid
from sqlalchemy import (
    String,
    DateTime,
    Uuid,
    ForeignKey,
    Integer,
    JSON,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.role import Role
    from app.models.department import Department


class ExternalDatabaseConnection(Base):
    __tablename__ = "external_database_connections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    engine: Mapped[str] = mapped_column(String, nullable=False)  # postgresql, mysql
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)  # encrypted
    ssl_mode: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    tenant: Mapped["Tenant"] = relationship("Tenant")
    schema_cache: Mapped[Optional["DatabaseSchemaCache"]] = relationship(
        "DatabaseSchemaCache",
        back_populates="connection",
        cascade="all, delete-orphan",
        uselist=False,
    )
    access_policies: Mapped[list["DatabaseAccessPolicy"]] = relationship(
        "DatabaseAccessPolicy",
        back_populates="connection",
        cascade="all, delete-orphan",
    )

    @property
    def table_count(self) -> int:
        if self.schema_cache and self.schema_cache.schema_data:
            return len(self.schema_cache.schema_data.get("tables", []))
        return 0


class DatabaseSchemaCache(Base):
    __tablename__ = "database_schema_caches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("external_database_connections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    schema_data: Mapped[dict] = mapped_column(JSON, nullable=False)
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
    connection: Mapped["ExternalDatabaseConnection"] = relationship(
        "ExternalDatabaseConnection", back_populates="schema_cache"
    )


class DatabaseAccessPolicy(Base):
    __tablename__ = "database_access_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("external_database_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    granted_via: Mapped[str] = mapped_column(
        String, nullable=False, server_default="direct"
    )  # direct, inherited, department
    inherited_from_role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("roles.id", ondelete="CASCADE"), nullable=True
    )
    granted_via_department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("departments.id", ondelete="CASCADE"), nullable=True
    )
    table_name: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # null means access to the whole DB
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Unique Constraint
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "role_id", "table_name", name="uq_db_conn_role_table"
        ),
    )

    # Relationships
    connection: Mapped["ExternalDatabaseConnection"] = relationship(
        "ExternalDatabaseConnection", back_populates="access_policies"
    )
    role: Mapped["Role"] = relationship("Role", foreign_keys=[role_id])
    inherited_from_role: Mapped[Optional["Role"]] = relationship(
        "Role", foreign_keys=[inherited_from_role_id]
    )
    granted_via_department: Mapped[Optional["Department"]] = relationship(
        "Department", foreign_keys=[granted_via_department_id]
    )
