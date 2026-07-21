# SQL agent node and SQL judge node

import uuid
import time
import json
from app.db.session import SessionLocal
from app.services.agents.types import AgentState, SQLAgentResult
from app.models.user import User
from app.models.external_database import (
    ExternalDatabaseConnection,
    DatabaseSchemaCache,
    DatabaseAccessPolicy,
)
import re
from app.services import database_service
from app.core.config import settings
import app.services.rag_service as rag_service

logger = rag_service.logger


async def _call_judge_llm(
    query: str, sql_query: str, query_results: list[dict]
) -> dict:
    """Calls Anthropic Claude Haiku in a non-blocking async way to judge result quality."""
    try:
        client = rag_service._get_async_anthropic_client()

        judge_system = (
            "You are a result quality evaluator. Given a user query, the SQL that was executed, "
            "and the results returned, evaluate whether the results sufficiently answer the user's question. "
            "Respond ONLY with a JSON object in this exact format with no other text:\n"
            '{"sufficient": true/false, "confidence": 0.0-1.0, "reasoning": "one sentence explanation", '
            '"fix_instruction": "if not sufficient, one sentence on what SQL change would fix it, else empty string"}'
        )

        judge_prompt = f"""User Query: {query}
        SQL Executed: {sql_query}
        Results (first 10 rows): {json.dumps(query_results[:10], default=str)}
        Row count: {len(query_results)}"""

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=judge_system,
            messages=[{"role": "user", "content": judge_prompt}],
        )

        text = response.content[0].text.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
        judgment = json.loads(text)

        if (
            "sufficient" not in judgment
            or "confidence" not in judgment
            or "reasoning" not in judgment
        ):
            raise ValueError("Invalid JSON keys in judge response")
        return judgment
    except Exception as exc:
        logger.warning("Judge LLM call failed or parsed incorrectly: %s", exc)
        return {
            "sufficient": True,
            "confidence": 0.7,
            "reasoning": "Judge unavailable",
            "fix_instruction": "",
        }


def get_db_session():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


async def sql_node(state: AgentState) -> dict:
    print(f"[SQL Node] Attempt {state['sql_attempts'] + 1}/{state['sql_max_attempts']}")
    db = get_db_session()
    try:
        query = state["query"]
        database_id = state["database_id"]
        model_id = state["model_id"]
        session_id = state["session_id"]
        sql_attempts = state["sql_attempts"]
        sql_fix_instruction = state["sql_fix_instruction"]

        attempt_num = sql_attempts + 1

        # Fetch user
        user = db.query(User).filter(User.id == uuid.UUID(state["user_id"])).first()
        if not user:
            return {
                "sql_result": SQLAgentResult(success=False, error="User not found"),
                "sql_attempts": attempt_num,
                "progress_tokens": [
                    "*Database query failed. Falling back to documents...*\n\n"
                ],
            }

        if not database_id:
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="Database ID is missing"
                ),
                "sql_attempts": attempt_num,
                "progress_tokens": [
                    "*Database query failed. Falling back to documents...*\n\n"
                ],
            }

        db_id_uuid = (
            uuid.UUID(database_id) if isinstance(database_id, str) else database_id
        )

        # Connection lookup
        connection = (
            db.query(ExternalDatabaseConnection)
            .filter(
                ExternalDatabaseConnection.id == db_id_uuid,
                ExternalDatabaseConnection.tenant_id == user.tenant_id,
            )
            .first()
        )
        if not connection:
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="Database connection not found"
                ),
                "sql_attempts": attempt_num,
                "progress_tokens": [
                    "*Database query failed. Falling back to documents...*\n\n"
                ],
            }

        # Check DB access
        if not database_service.check_user_db_access(db, user, db_id_uuid):
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="Database access denied"
                ),
                "sql_attempts": attempt_num,
                "progress_tokens": [
                    "*Database query failed. Falling back to documents...*\n\n"
                ],
            }

        # Schema cache lookup
        schema_cache = (
            db.query(DatabaseSchemaCache)
            .filter(DatabaseSchemaCache.connection_id == db_id_uuid)
            .first()
        )
        if not schema_cache or not schema_cache.schema_data:
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="Database schema missing"
                ),
                "sql_attempts": attempt_num,
                "progress_tokens": [
                    "*Database query failed. Falling back to documents...*\n\n"
                ],
            }

        all_tables = [t["name"] for t in schema_cache.schema_data.get("tables", [])]
        authorized_table_names = database_service.get_user_authorized_tables(
            db, user, db_id_uuid, all_tables
        )
        if not authorized_table_names:
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="No authorized tables"
                ),
                "sql_attempts": attempt_num,
                "progress_tokens": [
                    "*Database query failed. Falling back to documents...*\n\n"
                ],
            }

        # Authorized tables/columns resolution
        policies = []
        if not user.role.is_admin:
            policies = (
                db.query(DatabaseAccessPolicy)
                .filter(
                    DatabaseAccessPolicy.connection_id == db_id_uuid,
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
                    auth_cols = database_service.get_user_authorized_columns_for_table(
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
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="No authorized columns"
                ),
                "sql_attempts": attempt_num,
                "progress_tokens": [
                    "*Database query failed. Falling back to documents...*\n\n"
                ],
            }

        filtered_schema_data = {"tables": authorized_tables_info}

        # Session history
        session_id_uuid = (
            uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        )
        turns = []
        if session_id_uuid:
            turns = rag_service.get_recent_turns(
                db, session_id_uuid, settings.SQL_HISTORY_LIMIT
            )

        # Single attempt translate & run
        failed_sql = None
        error_message = None
        if attempt_num > 1:
            failed_sql = (
                state["sql_result"].sql_query if state.get("sql_result") else None
            )
            error_message = sql_fix_instruction

        model_id_uuid = uuid.UUID(model_id) if isinstance(model_id, str) else model_id

        try:
            sql_query = await database_service.translate_nl_to_sql(
                query=query,
                schema_data_filtered=filtered_schema_data,
                engine_type=connection.engine,
                db=db,
                model_id=model_id_uuid,
                failed_sql=failed_sql,
                error_message=error_message,
                conversation_history=turns,
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            print(f"[SQL Node] Generated SQL: {sql_query}")

            # Column guardrail check
            if not user.role.is_admin:
                database_service.check_sql_authorized_columns(
                    sql_query=sql_query,
                    engine_type=connection.engine,
                    authorized_cols_by_table=authorized_cols_by_table,
                    valid_tables=valid_tables,
                    all_physical_cols_by_table=all_physical_cols_by_table,
                )

            # Query execution
            start_time = time.perf_counter()
            query_results = database_service.run_query_on_connection(
                connection=connection,
                sql_query=sql_query,
                schema_cache_tables=schema_cache.schema_data.get("tables", []),
            )
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            print(
                f"[SQL Node] Rows returned: {len(query_results)}, Time: {execution_time_ms}ms"
            )

            return {
                "sql_result": SQLAgentResult(
                    success=True,
                    sql_query=sql_query,
                    query_results=query_results,
                    formatted_results=json.dumps(query_results, indent=2, default=str),
                    connection_name=connection.name,
                    connection_id=connection.id,
                    execution_time_ms=execution_time_ms,
                    attempts=attempt_num,
                ),
                "sql_attempts": attempt_num,
                "progress_tokens": [
                    f"**Generated SQL Query:**\n```sql\n{sql_query}\n```\n\n*Executing query...*\n\n"
                ],
            }
        except Exception as e:
            print(f"[SQL Node] Exception: {e}")
            return {
                "sql_result": SQLAgentResult(success=False, error=str(e)),
                "sql_attempts": attempt_num,
                "progress_tokens": [
                    "*Database query failed. Falling back to documents...*\n\n"
                ],
            }
    finally:
        db.close()


async def sql_judge_node(state: AgentState) -> dict:
    sql_result = state.get("sql_result")
    if not sql_result or not sql_result.success:
        return {
            "sql_sufficient": False,
            "sql_judge_reasoning": sql_result.error
            if sql_result
            else "SQL execution failed.",
            "sql_fix_instruction": "",
        }

    # Call judge LLM
    query_results = sql_result.query_results or []
    if not query_results:
        judgment = {
            "sufficient": False,
            "confidence": 0.0,
            "reasoning": "No matching records found in database.",
            "fix_instruction": "Try adjusting filters or search criteria.",
        }
    else:
        judgment = await _call_judge_llm(
            query=state["query"],
            sql_query=sql_result.sql_query,
            query_results=query_results,
        )

    print(
        f"[SQL Judge] sufficient={judgment['sufficient']}, confidence={judgment['confidence']}"
    )
    print(f"[SQL Judge] reasoning: {judgment['reasoning']}")

    # Merge results preserving SQLAgentResult
    updated_dict = {**sql_result.__dict__}
    updated_dict["confidence"] = judgment["confidence"]
    updated_dict["reasoning"] = judgment["reasoning"]

    return {
        "sql_sufficient": judgment["sufficient"],
        "sql_judge_reasoning": judgment["reasoning"],
        "sql_fix_instruction": judgment.get("fix_instruction", ""),
        "sql_result": SQLAgentResult(**updated_dict),
    }
