import uuid
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel


class DatabaseStatusResponse(BaseModel):
    connection_id: uuid.UUID
    name: str
    db_type: str
    host: str
    database_name: str
    status: str  # "active" | "unreachable" | "degraded"
    last_successful_query_at: Optional[datetime]
    schema_last_introspected_at: Optional[datetime]
    total_queries: int


class QueryMetricSummary(BaseModel):
    total: int
    last_7_days: int
    last_30_days: int


class QuerySuccessRate(BaseModel):
    success_count: int
    failed_count: int
    success_rate_percentage: float


class FailureReasonBreakdown(BaseModel):
    Ambiguous: int
    SQL_Error: int = 0  # To handle "SQL Error" mapping cleanly in JSON keys
    Unauthorized_Column: int = (
        0  # To handle "Unauthorized Column" mapping cleanly in JSON keys
    )
    Timeout: int
    Other: int


class QueryVolumeDay(BaseModel):
    date: str  # YYYY-MM-DD
    count: int


class ConnectionAnalyticsBreakdown(BaseModel):
    connection_id: uuid.UUID
    name: str
    total_queries: int
    success_count: int
    failed_count: int
    success_rate_percentage: float


class DatabaseAnalyticsResponse(BaseModel):
    metrics: QueryMetricSummary
    success_rate: QuerySuccessRate
    failure_reasons: Dict[str, int]
    query_volume: List[QueryVolumeDay]
    connections: List[ConnectionAnalyticsBreakdown]


class QueryHistoryItem(BaseModel):
    timestamp: datetime
    user_email: str
    user_name: str
    natural_language_query: str
    generated_sql: Optional[str]
    execution_time_ms: int
    status: str  # "success" | "failed"
    error_message: Optional[str]


class PaginatedQueryHistoryResponse(BaseModel):
    items: List[QueryHistoryItem]
    total: int
    page: int
    pages: int
    has_more: bool


class ColumnSchema(BaseModel):
    name: str
    type: str


class ForeignKeySchema(BaseModel):
    constrained_columns: List[str]
    referred_table: str
    referred_columns: List[str]


class TableSchema(BaseModel):
    table_name: str
    columns: List[ColumnSchema]
    primary_key: Optional[List[str]] = None
    foreign_keys: Optional[List[ForeignKeySchema]] = None
