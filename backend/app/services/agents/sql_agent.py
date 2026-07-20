import uuid
import time
import json
import re
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
            model="claude-3-5-haiku-20241022",
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


async def run_sql_agent(
    query: str,
    user: User,
    db: Session,
    database_id: uuid.UUID,
    model_id: Optional[uuid.UUID],
    session_id: Optional[uuid.UUID],
    instruction: Optional[str] = None,
    max_attempts: int = 3,
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

    print(f"[SQL Agent] Authorized tables: {authorized_table_names}")

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

    filtered_schema_data = {"tables": authorized_tables_info}

    turns = []
    if session_id:
        turns = rag_service.get_recent_turns(db, session_id, settings.SQL_HISTORY_LIMIT)

    attempt = 1
    previous_sql = None
    previous_error = None
    previous_results = None
    execution_time_ms = 0
    sql_query = None
    query_results = None
    judgment = {
        "sufficient": False,
        "confidence": 0.0,
        "reasoning": "No attempts completed",
        "fix_instruction": "",
    }

    if instruction:
        previous_error = f"Orchestrator instruction: {instruction}"

    while attempt <= max_attempts:
        # REASON
        if attempt >= 2:
            print(
                f"[SQL Agent] Attempt {attempt}/{max_attempts}. Reasoning about previous failure..."
            )

        # ACT
        try:
            previous_results_summary = ""
            if previous_results is not None:
                previous_results_summary = f"Previous results row count: {len(previous_results)}. Sample: {json.dumps(previous_results[:3], default=str)}"
            else:
                previous_results_summary = "No previous results returned."

            feedback_msg = None
            if previous_error:
                feedback_msg = (
                    f"Previous error: {previous_error}. {previous_results_summary}"
                )

            sql_query = await rag_service.translate_nl_to_sql(
                query=query,
                schema_data_filtered=filtered_schema_data,
                engine_type=connection.engine,
                db=db,
                model_id=model_id,
                failed_sql=previous_sql,
                error_message=feedback_msg,
                conversation_history=turns,
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            print(f"[SQL Agent] Attempt {attempt} - Generated SQL: {sql_query}")

            # Guardrail check
            access_denied_error = None
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
                print("[SQL Agent] Self-correction triggered. Reason: access denied")
                yield {
                    "type": "token",
                    "content": "\n*Attempting self-correction to find an alternative authorized query path...*\n\n",
                }
                previous_sql = sql_query
                previous_error = f"Access denied guardrail: {str(access_denied_error)}"
                previous_results = None
                attempt += 1
                continue

            yield {
                "type": "token",
                "content": f"**Generated SQL Query:**\n```sql\n{sql_query}\n```\n\n*Executing query...*\n\n",
            }

            start_time = time.perf_counter()
            query_results = rag_service.run_query_on_connection(
                connection=connection,
                sql_query=sql_query,
                schema_cache_tables=schema_cache.schema_data.get("tables", []),
            )
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            print(
                f"[SQL Agent] Attempt {attempt} - Execution complete. Rows: {len(query_results)}, Time: {execution_time_ms}ms"
            )

        except Exception as e:
            if rag_service.is_value_mismatch_error(connection.engine, e):
                print(
                    f"[SQL Agent] Self-correction triggered. Reason: value mismatch error: {e}"
                )
                yield {
                    "type": "token",
                    "content": f"\n*Database reported a value/literal mismatch error: {str(e)}.*\n*Attempting self-correction (retry 1/1)...*\n\n",
                }
            else:
                print(
                    f"[SQL Agent] Self-correction triggered. Reason: execution error: {e}"
                )
                yield {
                    "type": "token",
                    "content": "\n*Database query execution failed. Attempting self-correction...*\n\n",
                }

            previous_sql = sql_query if sql_query else None
            previous_error = f"SQL execution error: {str(e)}"
            previous_results = None
            attempt += 1
            continue

        # OBSERVE
        judgment = await _call_judge_llm(query, sql_query, query_results)
        print(
            f"[SQL Agent] Judge evaluation - sufficient: {judgment['sufficient']}, confidence: {judgment['confidence']}"
        )
        print(f"[SQL Agent] Judge reasoning: {judgment['reasoning']}")

        # DECIDE
        if judgment["sufficient"] or attempt == max_attempts:
            break
        else:
            print(
                f"[SQL Agent] Result insufficient. Retrying with fix: {judgment['fix_instruction']}"
            )
            previous_sql = sql_query
            previous_error = judgment["fix_instruction"]
            previous_results = query_results
            attempt += 1

    if judgment["sufficient"]:
        print(f"[SQL Agent] Result sufficient. Returning after {attempt} attempt(s).")
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
                confidence=judgment.get("confidence", 1.0),
                reasoning=judgment.get("reasoning", ""),
                attempts=attempt,
            ),
        }
    else:
        print(
            f"[SQL Agent] All {max_attempts} attempts exhausted. Returning best available result."
        )
        yield {
            "type": "agent_result",
            "result": SQLAgentResult(
                success=False,
                sql_query=sql_query,
                query_results=query_results,
                formatted_results=json.dumps(query_results, indent=2, default=str)
                if query_results
                else None,
                connection_name=connection.name,
                connection_id=connection.id,
                execution_time_ms=execution_time_ms,
                confidence=judgment.get("confidence", 0.0),
                reasoning=f"Exhausted {max_attempts} attempts. Last judge reasoning: {judgment.get('reasoning', '')}",
                attempts=attempt,
                error="Max attempts reached without sufficient result.",
            ),
        }
