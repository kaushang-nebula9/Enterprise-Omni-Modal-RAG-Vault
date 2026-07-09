import uuid
from datetime import datetime
from typing import Optional, Any, List
from pydantic import BaseModel, Field, model_validator
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
    table_count: int = 0

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def resolve_table_count(cls, data: Any) -> Any:
        if isinstance(data, dict):
            schema_cache = data.get("schema_cache")
            if schema_cache:
                schema_data = schema_cache.get("schema_data", {})
                data["table_count"] = len(schema_data.get("tables", []))
            elif "table_count" not in data:
                data["table_count"] = 0
        return data


class DatabaseAccessPolicyCreate(BaseModel):
    role_id: Optional[uuid.UUID] = None
    role_ids: Optional[List[uuid.UUID]] = None
    department_id: Optional[uuid.UUID] = None
    department_ids: Optional[List[uuid.UUID]] = None
    table_name: Optional[str] = None  # null scopes to the whole DB
    table_names: Optional[List[str]] = None
    columns: Optional[List[str]] = None


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
    columns: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True
