import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.enums import DatabaseEngine


class DatabaseConnectionTestRequest(BaseModel):
    engine: DatabaseEngine
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    database_name: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    ssl_mode: Optional[str] = "prefer"


class DatabaseConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1)
    engine: DatabaseEngine
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    database_name: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    ssl_mode: Optional[str] = "prefer"


class DatabaseConnectionUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None  # decrypted and re-encrypted if changed
    ssl_mode: Optional[str] = None


class DatabaseConnectionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    engine: str
    host: str
    port: int
    database_name: str
    username: str
    ssl_mode: Optional[str]
    status: str
    last_error: Optional[str]
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatabaseAccessPolicyCreate(BaseModel):
    role_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None
    table_name: Optional[str] = None  # null scopes to the whole DB


class DatabaseAccessPolicyResponse(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    role_id: uuid.UUID
    role_name: str
    granted_via: str
    inherited_from_role_id: Optional[uuid.UUID] = None
    inherited_from_role_name: Optional[str] = None
    granted_via_department_id: Optional[uuid.UUID] = None
    granted_via_department_name: Optional[str] = None
    table_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
