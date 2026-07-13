import uuid
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import List
import logging

from fastapi import APIRouter, Depends, HTTPException, status
import sqlalchemy as sa
from sqlalchemy import func, create_engine, text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.external_database import ExternalDatabaseConnection, DatabaseSchemaCache
from app.models.db_query_log import DBQueryLog
from app.schemas.database_health import (
    DatabaseStatusResponse,
    DatabaseAnalyticsResponse,
    PaginatedQueryHistoryResponse,
    TableSchema,
)
from app.services.database_service import (
    introspect_schema_live,
    decrypt_password,
    get_connection_url,
)
from app.services.audit_log_service import log_audit_event

logger = logging.getLogger(__name__)

router = APIRouter()


def ping_connection_status(connection: ExternalDatabaseConnection) -> str:
    """
    Pings a database connection and returns:
    - "active" if it successfully connects and runs SELECT 1
    - "degraded" if it successfully connects but query execution fails
    - "unreachable" if it fails to establish a connection
    """
    try:
        password_decrypted = decrypt_password(connection.password)
        url = get_connection_url(
            engine_type=connection.engine,
            host=connection.host,
            port=connection.port,
            database_name=connection.database_name,
            username=connection.username,
            password_decrypted=password_decrypted,
            ssl_mode=connection.ssl_mode,
        )

        connect_args = {}
        if connection.engine == "postgresql":
            connect_args = {"connect_timeout": 5}
        elif connection.engine == "mysql":
            connect_args = {"connect_timeout": 5}

        engine = create_engine(url, connect_args=connect_args)
        connected = False
        try:
            with engine.connect() as conn:
                connected = True
                conn.execute(text("SELECT 1"))
            return "active"
        except Exception as query_err:
            logger.warning(
                f"Ping execution failed for connection {connection.id}: {query_err}"
            )
            if connected:
                return "degraded"
            return "unreachable"
        finally:
            engine.dispose()
    except Exception as conn_err:
        logger.warning(
            f"Ping connection establishment failed for connection {connection.id}: {conn_err}"
        )
        return "unreachable"


@router.get("/status", response_model=List[DatabaseStatusResponse])
def get_database_status(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Retrieve reachability and sync metadata for all connections in the tenant.
    """
    connections = (
        db.query(ExternalDatabaseConnection)
        .filter(ExternalDatabaseConnection.tenant_id == current_admin.tenant_id)
        .all()
    )

    if not connections:
        return []

    # Perform reachability checks in parallel to save time
    with ThreadPoolExecutor(max_workers=min(len(connections), 10)) as executor:
        statuses = list(executor.map(ping_connection_status, connections))

    response_items = []
    for conn, status_val in zip(connections, statuses):
        # Fetch last successful query timestamp from db_query_logs
        last_success = (
            db.query(DBQueryLog.created_at)
            .filter(
                DBQueryLog.db_connection_id == conn.id,
                DBQueryLog.status == "success",
            )
            .order_by(DBQueryLog.created_at.desc())
            .first()
        )
        last_successful_query_at = last_success[0] if last_success else None

        # Fetch schema cached timestamp
        schema_cache = (
            db.query(DatabaseSchemaCache.updated_at)
            .filter(DatabaseSchemaCache.connection_id == conn.id)
            .first()
        )
        schema_last_introspected_at = schema_cache[0] if schema_cache else None

        # Fetch total queries count
        total_queries = (
            db.query(DBQueryLog.id)
            .filter(DBQueryLog.db_connection_id == conn.id)
            .count()
        )

        response_items.append(
            DatabaseStatusResponse(
                connection_id=conn.id,
                name=conn.name,
                db_type=conn.engine,
                host=conn.host,
                database_name=conn.database_name,
                status=status_val,
                last_successful_query_at=last_successful_query_at,
                schema_last_introspected_at=schema_last_introspected_at,
                total_queries=total_queries,
            )
        )

    return response_items


@router.get("/analytics", response_model=DatabaseAnalyticsResponse)
def get_database_analytics(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Fetch aggregated and per-connection query metrics for the tenant's databases.
    """
    connections = (
        db.query(ExternalDatabaseConnection)
        .filter(ExternalDatabaseConnection.tenant_id == current_admin.tenant_id)
        .all()
    )

    connection_ids = [c.id for c in connections]

    # Initialize empty analytics if no databases connected
    if not connection_ids:
        return {
            "metrics": {"total": 0, "last_7_days": 0, "last_30_days": 0},
            "success_rate": {
                "success_count": 0,
                "failed_count": 0,
                "success_rate_percentage": 0.0,
            },
            "failure_reasons": {
                "Ambiguous": 0,
                "SQL Error": 0,
                "Unauthorized Column": 0,
                "Timeout": 0,
                "Other": 0,
            },
            "query_volume": [],
            "connections": [],
        }

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # 1. Stat boxes counts
    total = (
        db.query(DBQueryLog)
        .filter(DBQueryLog.db_connection_id.in_(connection_ids))
        .count()
    )
    last_7_days = (
        db.query(DBQueryLog)
        .filter(
            DBQueryLog.db_connection_id.in_(connection_ids),
            DBQueryLog.created_at >= seven_days_ago,
        )
        .count()
    )
    last_30_days = (
        db.query(DBQueryLog)
        .filter(
            DBQueryLog.db_connection_id.in_(connection_ids),
            DBQueryLog.created_at >= thirty_days_ago,
        )
        .count()
    )

    # 2. Success/failure ratios
    success_count = (
        db.query(DBQueryLog)
        .filter(
            DBQueryLog.db_connection_id.in_(connection_ids),
            DBQueryLog.status == "success",
        )
        .count()
    )
    failed_count = (
        db.query(DBQueryLog)
        .filter(
            DBQueryLog.db_connection_id.in_(connection_ids),
            DBQueryLog.status == "failed",
        )
        .count()
    )

    total_with_status = success_count + failed_count
    success_rate_percentage = (
        round((success_count / total_with_status) * 100, 2)
        if total_with_status > 0
        else 0.0
    )

    # 3. Failure reasons breakdown
    failure_groups = (
        db.query(DBQueryLog.error_type, func.count(DBQueryLog.id))
        .filter(
            DBQueryLog.db_connection_id.in_(connection_ids),
            DBQueryLog.status == "failed",
        )
        .group_by(DBQueryLog.error_type)
        .all()
    )

    reasons_breakdown = {
        "Ambiguous": 0,
        "SQL Error": 0,
        "Unauthorized Column": 0,
        "Timeout": 0,
        "Other": 0,
    }
    for err_type, count in failure_groups:
        key = err_type or "Other"
        # Standardize formatting
        if key == "SQL_Error":
            key = "SQL Error"
        elif key == "Unauthorized_Column":
            key = "Unauthorized Column"

        if key in reasons_breakdown:
            reasons_breakdown[key] += count
        else:
            reasons_breakdown["Other"] += count

    # 4. Query volume by day (last 30 days)
    volume_by_day = (
        db.query(
            func.cast(DBQueryLog.created_at, sa.Date).label("day"),
            func.count(DBQueryLog.id).label("count"),
        )
        .filter(
            DBQueryLog.db_connection_id.in_(connection_ids),
            DBQueryLog.created_at >= thirty_days_ago,
        )
        .group_by(func.cast(DBQueryLog.created_at, sa.Date))
        .all()
    )

    # Pre-populate all last 30 days with count 0 to cover gaps
    day_map = {}
    for i in range(30):
        d_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_map[d_str] = 0

    for day, count in volume_by_day:
        d_str = day.strftime("%Y-%m-%d")
        if d_str in day_map:
            day_map[d_str] = count

    query_volume = [{"date": k, "count": v} for k, v in sorted(day_map.items())]

    # 5. Connection breakdowns
    connection_breakdown = []
    for conn in connections:
        c_total = (
            db.query(DBQueryLog).filter(DBQueryLog.db_connection_id == conn.id).count()
        )
        c_success = (
            db.query(DBQueryLog)
            .filter(
                DBQueryLog.db_connection_id == conn.id,
                DBQueryLog.status == "success",
            )
            .count()
        )
        c_failed = (
            db.query(DBQueryLog)
            .filter(
                DBQueryLog.db_connection_id == conn.id,
                DBQueryLog.status == "failed",
            )
            .count()
        )
        c_pct = round((c_success / c_total) * 100, 2) if c_total > 0 else 0.0

        connection_breakdown.append(
            {
                "connection_id": conn.id,
                "name": conn.name,
                "total_queries": c_total,
                "success_count": c_success,
                "failed_count": c_failed,
                "success_rate_percentage": c_pct,
            }
        )

    return {
        "metrics": {
            "total": total,
            "last_7_days": last_7_days,
            "last_30_days": last_30_days,
        },
        "success_rate": {
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate_percentage": success_rate_percentage,
        },
        "failure_reasons": reasons_breakdown,
        "query_volume": query_volume,
        "connections": connection_breakdown,
    }


@router.get(
    "/connections/{connection_id}/queries",
    response_model=PaginatedQueryHistoryResponse,
)
def get_connection_queries(
    connection_id: uuid.UUID,
    page: int = 1,
    limit: int = 50,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get paginated query executions for a single database connection.
    """
    conn = (
        db.query(ExternalDatabaseConnection)
        .filter(
            ExternalDatabaseConnection.id == connection_id,
            ExternalDatabaseConnection.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection not found",
        )

    offset = (page - 1) * limit
    base_query = db.query(DBQueryLog).filter(
        DBQueryLog.db_connection_id == connection_id
    )

    total = base_query.count()
    logs = (
        base_query.order_by(DBQueryLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for log in logs:
        items.append(
            {
                "timestamp": log.created_at,
                "user_email": log.user.email if log.user else "unknown@example.com",
                "user_name": log.user.full_name if log.user else "Unknown User",
                "natural_language_query": log.natural_language_query,
                "generated_sql": log.generated_sql,
                "execution_time_ms": log.execution_time_ms,
                "status": log.status,
                "error_message": log.error_message,
            }
        )

    pages = (total + limit - 1) // limit
    has_more = page < pages

    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": pages,
        "has_more": has_more,
    }


@router.get("/connections/{connection_id}/schema", response_model=List[TableSchema])
def get_connection_schema(
    connection_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Fetch introspected tables and column metadata from the cache.
    """
    conn = (
        db.query(ExternalDatabaseConnection)
        .filter(
            ExternalDatabaseConnection.id == connection_id,
            ExternalDatabaseConnection.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection not found",
        )

    cache = (
        db.query(DatabaseSchemaCache)
        .filter(DatabaseSchemaCache.connection_id == connection_id)
        .first()
    )

    if not cache or not cache.schema_data:
        return []

    tables = cache.schema_data.get("tables", [])
    result = []
    for t in tables:
        result.append(
            TableSchema(
                table_name=t.get("name"),
                columns=[
                    {"name": col.get("name"), "type": col.get("type")}
                    for col in t.get("columns", [])
                ],
                primary_key=t.get("primary_key", []),
                foreign_keys=[
                    {
                        "constrained_columns": fk.get("constrained_columns", []),
                        "referred_table": fk.get("referred_table"),
                        "referred_columns": fk.get("referred_columns", []),
                    }
                    for fk in t.get("foreign_keys", [])
                ],
            )
        )

    return result


@router.post("/connections/{connection_id}/refresh-schema")
def refresh_connection_schema(
    connection_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Trigger manual schema sync/introspection. Reuses the core introspect_schema_live function.
    """
    conn = (
        db.query(ExternalDatabaseConnection)
        .filter(
            ExternalDatabaseConnection.id == connection_id,
            ExternalDatabaseConnection.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection not found",
        )

    try:
        pwd_decrypted = decrypt_password(conn.password)
        schema_data = introspect_schema_live(
            engine_type=conn.engine,
            host=conn.host,
            port=conn.port,
            database_name=conn.database_name,
            username=conn.username,
            password_decrypted=pwd_decrypted,
            ssl_mode=conn.ssl_mode,
        )

        cache = (
            db.query(DatabaseSchemaCache)
            .filter(DatabaseSchemaCache.connection_id == connection_id)
            .first()
        )

        if cache:
            cache.schema_data = schema_data
            cache.updated_at = datetime.now(timezone.utc)
        else:
            db.add(
                DatabaseSchemaCache(
                    connection_id=connection_id,
                    schema_data=schema_data,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )

        conn.status = "active"
        conn.last_error = None
        conn.last_synced_at = datetime.now(timezone.utc)
        db.commit()

        log_audit_event(
            db=db,
            tenant_id=current_admin.tenant_id,
            actor_user_id=current_admin.id,
            action="REFRESH_SCHEMA",
            description=f"Manually refreshed schema for database connection '{conn.name}'",
            metadata={"connection_id": str(conn.id)},
        )

        return {"status": "success", "message": "Schema refreshed successfully"}

    except Exception as e:
        conn.status = "error"
        conn.last_error = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schema refresh failed: {str(e)}",
        )
