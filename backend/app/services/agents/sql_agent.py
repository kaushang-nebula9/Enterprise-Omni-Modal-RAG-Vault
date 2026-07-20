import uuid
import time
import json
import logging
from typing import Optional, AsyncGenerator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.external_database import (
    ExternalDatabaseConnection,
    DatabaseSchemaCache,
    DatabaseAccessPolicy,
)
from app.services.database_service import (
    check_user_db_access,
    get_user_authorized_tables,
    get_user_authorized_columns_for_table,
    check_sql_authorized_columns,
)
import app.services.rag_service as rag_service
from app.services.agents.types import SQLAgentResult

logger = logging.getLogger(__name__)


async def run_sql_agent(
    query: str,
    user: User,
    db: Session,
    database_id: uuid.UUID,
    model_id: Optional[uuid.UUID],
    session_id: Optional[uuid.UUID],
) -> AsyncGenerator[dict, None]:
    print(f"[SQL Agent] Starting. database_id={database_id}")
    connection = (
        db.query(ExternalDatabaseConnection)
        .filter(
            ExternalDatabaseConnection.id == database_id,
            ExternalDatabaseConnection.tenant_id == user.tenant_id,
        )
        .first()
    )
    if not connection:
        error_reason = "Database connection not found"
        logger.info("Database connection not found, falling back to documents")
        yield {
            "type": "token",
            "content": "\n*Database connection not found. Searching documents...*\n\n",
        }
        print(f"[SQL Agent] Failed: {error_reason}. Returning failure result.")
        yield {
            "type": "agent_result",
            "result": SQLAgentResult(success=False, error=error_reason),
        }
        return

    print(f"[SQL Agent] Connection found: {connection.name}")

    if not check_user_db_access(db, user, database_id):
        error_reason = "Database access denied"
        logger.info("Database access denied, falling back to documents")
        yield {
            "type": "token",
            "content": "\n*Database access denied. Searching documents...*\n\n",
        }
        print(f"[SQL Agent] Failed: {error_reason}. Returning failure result.")
        yield {
            "type": "agent_result",
            "result": SQLAgentResult(success=False, error=error_reason),
        }
        return

    print("[SQL Agent] Access check passed.")

    schema_cache = (
        db.query(DatabaseSchemaCache)
        .filter(DatabaseSchemaCache.connection_id == database_id)
        .first()
    )
    if not schema_cache or not schema_cache.schema_data:
        error_reason = "Database schema missing"
        logger.info("Database schema missing, falling back to documents")
        yield {
            "type": "token",
            "content": "\n*Database schema missing. Searching documents...*\n\n",
        }
        print(f"[SQL Agent] Failed: {error_reason}. Returning failure result.")
        yield {
            "type": "agent_result",
            "result": SQLAgentResult(success=False, error=error_reason),
        }
        return

    all_tables = [t["name"] for t in schema_cache.schema_data.get("tables", [])]
    print(f"[SQL Agent] Schema cache loaded. Tables available: {len(all_tables)}")

    authorized_table_names = get_user_authorized_tables(
        db, user, database_id, all_tables
    )
    if not authorized_table_names:
        error_reason = "No authorized tables"
        logger.info("No authorized tables found, falling back to documents")
        yield {
            "type": "token",
            "content": "\n*No authorized tables in database. Searching documents...*\n\n",
        }
        print(f"[SQL Agent] Failed: {error_reason}. Returning failure result.")
        yield {
            "type": "agent_result",
            "result": SQLAgentResult(success=False, error=error_reason),
        }
        return

    print(f"[SQL Agent] Authorized tables resolved: {authorized_table_names}")

    policies = []
    if not user.role.is_admin:
        policies = (
            db.query(DatabaseAccessPolicy)
            .filter(
                DatabaseAccessPolicy.connection_id == database_id,
                DatabaseAccessPolicy.role_id == user.role_id,
            )
            .all()
        )

    authorized_cols_by_table = {}
    all_physical_cols_by_table = {}
    valid_tables = {
        t["name"].lower() for t in schema_cache.schema_data.get("tables", [])
    }
    authorized_tables_info = []

    for t in schema_cache.schema_data.get("tables", []):
        t_name = t["name"]
        if t_name in authorized_table_names:
            all_cols = [c["name"] for c in t.get("columns", [])]
            all_physical_cols_by_table[t_name.lower()] = set(
                c.lower() for c in all_cols
            )
            if user.role.is_admin:
                auth_cols = set(c.lower() for c in all_cols)
            else:
                auth_cols = get_user_authorized_columns_for_table(
                    policies, t_name, all_cols
                )

            if auth_cols or user.role.is_admin:
                authorized_cols_by_table[t_name.lower()] = auth_cols
                tbl_copy = dict(t)
                tbl_copy["columns"] = [
                    col
                    for col in t.get("columns", [])
                    if col["name"].lower() in auth_cols
                ]
                authorized_tables_info.append(tbl_copy)

    if not authorized_tables_info:
        error_reason = "No authorized columns"
        logger.info("No authorized columns/tables found, falling back to documents")
        yield {
            "type": "token",
            "content": "\n*No authorized columns in database. Searching documents...*\n\n",
        }
        print(f"[SQL Agent] Failed: {error_reason}. Returning failure result.")
        yield {
            "type": "agent_result",
            "result": SQLAgentResult(success=False, error=error_reason),
        }
        return

    # db_connection_id = connection.id
    filtered_schema_data = {"tables": authorized_tables_info}

    yield {
        "type": "token",
        "content": "*Thinking... Translating your request to SQL...*\n\n",
    }
    turns = []
    if session_id:
        turns = rag_service.get_recent_turns(db, session_id, settings.SQL_HISTORY_LIMIT)

    access_denied_error = None
    try:
        print("[SQL Agent] Translating NL to SQL...")
        sql_query = await rag_service.translate_nl_to_sql(
            query=query,
            schema_data_filtered=filtered_schema_data,
            engine_type=connection.engine,
            db=db,
            model_id=model_id,
            conversation_history=turns,
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        print(f"[SQL Agent] Generated SQL: {sql_query}")

        if not user.role.is_admin:
            try:
                check_sql_authorized_columns(
                    sql_query=sql_query,
                    engine_type=connection.engine,
                    authorized_cols_by_table=authorized_cols_by_table,
                    valid_tables=valid_tables,
                    all_physical_cols_by_table=all_physical_cols_by_table,
                )
            except ValueError as val_err:
                if "access denied" in str(val_err).lower():
                    access_denied_error = val_err
                else:
                    raise val_err

        if access_denied_error:
            logger.warning(
                f"Connection {connection.id} - SQL translation accessed unauthorized columns: {str(access_denied_error)}. "
                f"Original SQL: {sql_query}. Attempting self-correction for alternative path..."
            )
            print("[SQL Agent] Self-correction triggered. Reason: access denied")
            yield {
                "type": "token",
                "content": "\n*Attempting self-correction to find an alternative authorized query path...*\n\n",
            }

            try:
                sql_query = await rag_service.translate_nl_to_sql(
                    query=query,
                    schema_data_filtered=filtered_schema_data,
                    engine_type=connection.engine,
                    db=db,
                    model_id=model_id,
                    failed_sql=sql_query,
                    error_message=str(access_denied_error),
                    conversation_history=turns,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                )
                print(f"[SQL Agent] Self-correction succeeded. New SQL: {sql_query}")

                if not user.role.is_admin:
                    check_sql_authorized_columns(
                        sql_query=sql_query,
                        engine_type=connection.engine,
                        authorized_cols_by_table=authorized_cols_by_table,
                        valid_tables=valid_tables,
                        all_physical_cols_by_table=all_physical_cols_by_table,
                    )
            except Exception as retry_exc:
                logger.error(
                    f"Connection {connection.id} - SQL self-correction for access denied failed: {str(retry_exc)}. "
                    f"Reverting to original access denied error."
                )
                raise access_denied_error

        yield {
            "type": "token",
            "content": f"**Generated SQL Query:**\n```sql\n{sql_query}\n```\n\n*Executing query...*\n\n",
        }
    except Exception as e:
        error_reason = "SQL translation failed"
        logger.info(f"SQL translation failed, falling back to documents: {e}")
        yield {
            "type": "token",
            "content": "\n*Could not translate query to SQL. Searching documents...*\n\n",
        }
        print(f"[SQL Agent] Failed: {error_reason}. Returning failure result.")
        yield {
            "type": "agent_result",
            "result": SQLAgentResult(success=False, error=error_reason),
        }
        return

    try:
        print("[SQL Agent] Executing SQL query...")
        start_time = time.perf_counter()
        query_results = rag_service.run_query_on_connection(
            connection=connection,
            sql_query=sql_query,
            schema_cache_tables=schema_cache.schema_data.get("tables", []),
        )
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
    except Exception as e:
        if rag_service.is_value_mismatch_error(connection.engine, e):
            logger.warning(
                f"Connection {connection.id} - NL-to-SQL execution failed with value/literal mismatch: {str(e)}. "
                f"Original SQL: {sql_query}. Attempting self-correction..."
            )
            print(
                f"[SQL Agent] Self-correction triggered. Reason: value mismatch error: {e}"
            )
            yield {
                "type": "token",
                "content": f"\n*Database reported a value/literal mismatch error: {str(e)}.*\n*Attempting self-correction (retry 1/1)...*\n\n",
            }

            try:
                sql_query = await rag_service.translate_nl_to_sql(
                    query=query,
                    schema_data_filtered=filtered_schema_data,
                    engine_type=connection.engine,
                    db=db,
                    model_id=model_id,
                    failed_sql=sql_query,
                    error_message=str(e),
                    conversation_history=turns,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                )
                print(f"[SQL Agent] Self-correction succeeded. New SQL: {sql_query}")

                if not user.role.is_admin:
                    check_sql_authorized_columns(
                        sql_query=sql_query,
                        engine_type=connection.engine,
                        authorized_cols_by_table=authorized_cols_by_table,
                        valid_tables=valid_tables,
                        all_physical_cols_by_table=all_physical_cols_by_table,
                    )

                yield {
                    "type": "token",
                    "content": f"**Regenerated SQL Query:**\n```sql\n{sql_query}\n```\n\n*Executing corrected query...*\n\n",
                }

                print("[SQL Agent] Executing SQL query...")
                start_time = time.perf_counter()
                query_results = rag_service.run_query_on_connection(
                    connection=connection,
                    sql_query=sql_query,
                    schema_cache_tables=schema_cache.schema_data.get("tables", []),
                )
                execution_time_ms = int((time.perf_counter() - start_time) * 1000)

                logger.info(
                    f"Connection {connection.id} - NL-to-SQL self-correction successful. New SQL: {sql_query}"
                )

            except Exception as retry_err:
                error_reason = "Database query execution failed"
                logger.info(
                    f"SQL execution failed, falling back to documents: {retry_err}"
                )
                yield {
                    "type": "token",
                    "content": "\n*Database query execution failed. Searching documents...*\n\n",
                }
                print(f"[SQL Agent] Failed: {error_reason}. Returning failure result.")
                yield {
                    "type": "agent_result",
                    "result": SQLAgentResult(success=False, error=error_reason),
                }
                return
        else:
            error_reason = "Database query execution failed"
            logger.info(f"SQL execution failed, falling back to documents: {e}")
            yield {
                "type": "token",
                "content": "\n*Database query execution failed. Searching documents...*\n\n",
            }
            print(f"[SQL Agent] Failed: {error_reason}. Returning failure result.")
            yield {
                "type": "agent_result",
                "result": SQLAgentResult(success=False, error=error_reason),
            }
            return

    if not query_results or len(query_results) == 0:
        error_reason = "No results returned"
        logger.info("SQL query returned 0 results, falling back to documents")
        yield {
            "type": "token",
            "content": "\n*No matching records found in database. Searching documents...*\n\n",
        }
        print(f"[SQL Agent] Failed: {error_reason}. Returning failure result.")
        yield {
            "type": "agent_result",
            "result": SQLAgentResult(success=False, error=error_reason),
        }
        return

    print(
        "[SQL Agent] Query executed. Rows returned: {len(query_results)}. Time: {execution_time_ms}ms"
    )
    print("[SQL Agent] Done. Returning success result.")

    # Success case
    yield {
        "type": "agent_result",
        "result": SQLAgentResult(
            success=True,
            sql_query=sql_query,
            query_results=query_results,
            formatted_results=json.dumps(query_results, indent=2, default=str),
            connection_name=connection.name,
            connection_id=connection.id,
            execution_time_ms=execution_time_ms,
        ),
    }
