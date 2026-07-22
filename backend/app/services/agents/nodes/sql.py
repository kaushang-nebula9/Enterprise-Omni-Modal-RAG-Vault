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


async def gather_sql_context(state: AgentState, db) -> dict:
    """Plain async function to gather database context upfront before graph runs."""
    try:
        user_id = state.get("user_id")
        if not user_id:
            return {
                "sql_result": SQLAgentResult(success=False, error="User ID is missing"),
                "context_error": "User ID is missing",
            }
        user_id_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_id_uuid).first()
        if not user:
            return {
                "sql_result": SQLAgentResult(success=False, error="User not found"),
                "context_error": "User not found",
            }

        database_id = state.get("database_id")
        if not database_id:
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="Database ID is missing"
                ),
                "context_error": "Database ID is missing",
            }
        database_id_uuid = (
            uuid.UUID(database_id) if isinstance(database_id, str) else database_id
        )

        connection = (
            db.query(ExternalDatabaseConnection)
            .filter(
                ExternalDatabaseConnection.id == database_id_uuid,
                ExternalDatabaseConnection.tenant_id == user.tenant_id,
            )
            .first()
        )
        if not connection:
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="Database connection not found"
                ),
                "context_error": "Database connection not found",
            }

        if not database_service.check_user_db_access(db, user, database_id_uuid):
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="Database access denied"
                ),
                "context_error": "Database access denied",
            }

        schema_cache = (
            db.query(DatabaseSchemaCache)
            .filter(DatabaseSchemaCache.connection_id == database_id_uuid)
            .first()
        )
        if not schema_cache or not schema_cache.schema_data:
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="Database schema missing"
                ),
                "context_error": "Database schema missing",
            }

        all_tables = [t["name"] for t in schema_cache.schema_data.get("tables", [])]
        authorized_table_names = database_service.get_user_authorized_tables(
            db, user, database_id_uuid, all_tables
        )
        if not authorized_table_names:
            return {
                "sql_result": SQLAgentResult(
                    success=False, error="No authorized tables"
                ),
                "context_error": "No authorized tables",
            }

        policies = []
        if not user.role.is_admin:
            policies = (
                db.query(DatabaseAccessPolicy)
                .filter(
                    DatabaseAccessPolicy.connection_id == database_id_uuid,
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
                "context_error": "No authorized columns",
            }

        session_id = state.get("session_id")
        session_id_uuid = (
            uuid.UUID(session_id)
            if isinstance(session_id, str) and session_id
            else session_id
        )
        turns = []
        if session_id_uuid:
            turns = rag_service.get_recent_turns(
                db, session_id_uuid, settings.SQL_HISTORY_LIMIT
            )

        return {
            "db_user_id": str(user.id),
            "db_authorized_schema": {"tables": authorized_tables_info},
            "db_authorized_cols_by_table": authorized_cols_by_table,
            "db_all_physical_cols_by_table": all_physical_cols_by_table,
            "db_valid_tables": valid_tables,
            "db_connection_engine": connection.engine,
            "db_connection_name": connection.name,
            "db_connection_id": str(connection.id),
            "db_session_turns": turns,
            "context_error": None,
        }
    except Exception as exc:
        return {
            "sql_result": SQLAgentResult(success=False, error=str(exc)),
            "context_error": str(exc),
        }


SCHEMA_INTELLIGENCE_TOOLS = [
    {
        "name": "get_all_table_names",
        "description": "Returns only the names of every table the user is authorized to access. Contains no column details. Very cheap.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_table_schema",
        "description": "Returns the complete schema (columns, types, keys) only for the specified table names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of table names to get schema for, e.g. ['orders', 'customers']",
                }
            },
            "required": ["table_names"],
        },
    },
    {
        "name": "get_all_tables_schema",
        "description": "Returns the complete schema of every authorized table. This is expensive and should only be used if selective exploration is insufficient.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# TOOLS
def _execute_schema_tool(
    tool_name: str, tool_args: dict, authorized_tables: list[dict]
) -> str:
    # returns the names of all authorized tables
    if tool_name == "get_all_table_names":
        names = []
        for table in authorized_tables:
            if "name" in table:
                names.append(table["name"])
        return json.dumps(names)

    # returns the schema for the specified table names
    elif tool_name == "get_table_schema":
        table_names = tool_args.get("table_names", [])
        if isinstance(table_names, str):
            table_names = [table_names]
        requested_set = {str(name).lower() for name in table_names}
        matched = [
            t for t in authorized_tables if t.get("name", "").lower() in requested_set
        ]
        return json.dumps({"tables": matched}, default=str)

    # returns the schema for all authorized tables
    elif tool_name == "get_all_tables_schema":
        return json.dumps({"tables": authorized_tables}, default=str)
    else:
        return f"Unknown tool: {tool_name}"


def _parse_schema_selection_json(text: str) -> dict | None:
    # Return None if the response is empty.
    if not text:
        return None

    # Remove leading/trailing whitespace from the response.
    cleaned = text.strip()

    # Remove Markdown code block markers if the JSON is wrapped in them.
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # Try parsing the cleaned text directly as JSON.
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "selected_tables" in data:
            return data
    except Exception:
        pass

    # As a fallback, extract the first JSON object from the response.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        # Try parsing the extracted JSON object.
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and "selected_tables" in data:
                return data
        except Exception:
            pass

    # Return None if no valid schema selection JSON could be parsed.
    return None


async def schema_selection_node(state: AgentState) -> dict:
    """
    Schema Intelligence Agent following the ReAct pattern.
    Understands user intent and dynamically discovers database schema using tools
    until it has gathered sufficient context to stop.
    """
    if state.get("context_error"):
        return {}

    user_query = state.get("query", "")
    authorized_schema = state.get("db_authorized_schema") or {}
    authorized_tables = authorized_schema.get("tables", [])

    if not authorized_tables:
        print("[Schema Intelligence Agent] No authorized tables available.")
        return {"db_filtered_schema": {"tables": []}}

    history_turns = state.get("db_session_turns") or []
    history_str = ""

    # converting history turns to a string representation for the prompt
    if history_turns:
        history_str = (
            f"\nPrior Conversation Context:\n{json.dumps(history_turns, default=str)}\n"
        )

    system_prompt = (
        "You are a Schema Intelligence Agent operating in a ReAct (Reasoning + Acting) loop.\n"
        "Your objective is to identify the minimum set of database tables required for another agent to generate correct SQL for the user's query.\n"
        "You have access to tools for discovering database schema. At every step, reason about what information you currently have, what information is missing, and whether a tool call is necessary.\n\n"
        "Available tools:\n"
        "1. get_all_table_names\n"
        "   Returns all authorized table names.\n"
        "2. get_table_schema(table_names)\n"
        "   Returns the schema for the specified tables.\n"
        "3. get_all_tables_schema\n"
        "   Returns the schema for every authorized table.\n\n"
        "Rules:\n"
        "- Use tools only when they help you make a better decision.\n"
        "- Avoid unnecessary tool calls and avoid retrieving more schema than required.\n"
        "- When you are confident you have gathered enough schema context to answer the query, DO NOT call any more tools.\n"
        "- End your turn by returning ONLY a valid JSON object in this exact format with no extra commentary:\n"
        "{\n"
        '    "selected_tables": ["table1", "table2"],\n'
        '    "reasoning": "Short explanation of why these tables were chosen."\n'
        "}\n\n"
        "Do not continue exploring after reaching sufficient confidence."
    )

    user_prompt = (
        f"User Query: {user_query}\n"
        f"{history_str}\n"
        "Discover the schema step-by-step using tools and select only the required tables."
    )

    messages = [{"role": "user", "content": user_prompt}]
    selected_table_names = []
    agent_reasoning = ""
    reformat_attempted = False

    try:
        client = rag_service._get_async_anthropic_client()
        max_turns = 7

        for turn in range(max_turns):
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
                tools=SCHEMA_INTELLIGENCE_TOOLS,
            )

            # Store Claude's response
            assistant_content = response.content
            print(
                f"[Schema Intelligence Agent] LLM Response (Turn {turn + 1}): {assistant_content}"
            )
            # Save conversation history
            messages.append({"role": "assistant", "content": assistant_content})

            # Extract text blocks for logging
            text_blocks = [
                b.text
                for b in assistant_content
                if isinstance(getattr(b, "text", None), str) and b.text
            ]
            if text_blocks:
                print(
                    f"[Schema Intelligence Agent] ReAct Thought (Turn {turn + 1}): {' '.join(text_blocks)}"
                )

            # Find tool calls
            tool_use_blocks = [
                block
                for block in assistant_content
                if getattr(block, "type", None) == "tool_use"
            ]

            # Check whether it is finished
            if (
                not tool_use_blocks
                or getattr(response, "stop_reason", None) == "end_turn"
            ):
                full_text = " ".join(text_blocks)
                parsed = _parse_schema_selection_json(full_text)

                if parsed and "selected_tables" in parsed:
                    selected_table_names = parsed.get("selected_tables", [])
                    agent_reasoning = parsed.get("reasoning", "")
                    break

                # If JSON is invalid and we haven't tried reformatting yet, ask the model to reformat
                elif not reformat_attempted:
                    reformat_attempted = True
                    print(
                        "[Schema Intelligence Agent] Failed to parse JSON final answer. Prompting model to reformat."
                    )

                    # Ask LLM to reformat
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous response could not be parsed as valid JSON. "
                                "Please respond ONLY with a valid JSON object with keys 'selected_tables' (list of strings) and 'reasoning' (string)."
                            ),
                        }
                    )
                    continue
                else:
                    break

            tool_results = []

            # Loop through every requested tool and execute it
            for block in tool_use_blocks:
                tool_name = block.name
                tool_args = block.input or {}
                print(
                    f"[Schema Intelligence Agent] Tool Call (Turn {turn + 1}): {tool_name}({tool_args})"
                )

                res_str = _execute_schema_tool(tool_name, tool_args, authorized_tables)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": res_str,
                    }
                )

            # Give tool result back to Claude
            messages.append({"role": "user", "content": tool_results})

    except Exception as exc:
        logger.warning(
            f"[Schema Intelligence Agent] Exception during ReAct loop: {exc}"
        )

    # Process and filter final schema based on agent decision
    selected_set = {t.lower() for t in selected_table_names}
    filtered_tables = [
        t for t in authorized_tables if t.get("name", "").lower() in selected_set
    ]

    # If LLM somehow selected no valid tables, fall back to Entire authorized schema
    if not filtered_tables:
        print(
            "[Schema Intelligence Agent] No valid tables selected or matched; falling back to full authorized schema."
        )
        filtered_schema = authorized_schema
    else:
        filtered_schema = {"tables": filtered_tables}

    chosen_names = [t.get("name") for t in filtered_schema.get("tables", [])]
    print(f"[Schema Intelligence Agent] Final Selected Tables: {chosen_names}")
    if agent_reasoning:
        print(f"[Schema Intelligence Agent] Reasoning: {agent_reasoning}")

    progress_msg = f"**Schema Intelligence Agent:** Selected table(s) `{', '.join(chosen_names)}` for query resolution.\n\n"

    return {
        "db_filtered_schema": filtered_schema,
        "progress_tokens": [progress_msg],
    }


async def sql_generation_node(state: AgentState) -> dict:
    if state.get("context_error"):
        return {
            "sql_result": SQLAgentResult(success=False, error=state["context_error"]),
            "sql_generation_error": state["context_error"],
        }

    query = state["query"]
    filtered_schema = (
        state.get("db_filtered_schema") or state.get("db_authorized_schema") or {}
    )
    generation_attempts = state["sql_generation_attempts"]
    previous_sql = state.get("generated_sql")
    sql_generation_error = state.get("sql_generation_error")

    model_id = state.get("model_id")
    model_id_uuid = (
        uuid.UUID(model_id) if isinstance(model_id, str) and model_id else model_id
    )

    user_id = state.get("user_id")
    user_id_uuid = (
        uuid.UUID(user_id) if isinstance(user_id, str) and user_id else user_id
    )

    tenant_id = state.get("tenant_id")
    tenant_id_uuid = (
        uuid.UUID(tenant_id) if isinstance(tenant_id, str) and tenant_id else tenant_id
    )

    db = get_db_session()
    try:
        sql_query = await database_service.translate_nl_to_sql(
            query=query,
            schema_data_filtered=filtered_schema,
            engine_type=state["db_connection_engine"],
            db=db,
            model_id=model_id_uuid,
            failed_sql=previous_sql if generation_attempts > 0 else None,
            error_message=sql_generation_error if generation_attempts > 0 else None,
            conversation_history=state.get("db_session_turns"),
            user_id=user_id_uuid,
            tenant_id=tenant_id_uuid,
        )

        user = (
            db.query(User).filter(User.id == user_id_uuid).first()
            if user_id_uuid
            else None
        )
        is_admin = user.role.is_admin if user and user.role else False

        if not is_admin:
            database_service.check_sql_authorized_columns(
                sql_query=sql_query,
                engine_type=state["db_connection_engine"],
                authorized_cols_by_table=state["db_authorized_cols_by_table"],
                valid_tables=state["db_valid_tables"],
                all_physical_cols_by_table=state["db_all_physical_cols_by_table"],
            )

        print(f"[SQL Generation] Attempt {generation_attempts + 1}, SQL: {sql_query}")
        return {
            "generated_sql": sql_query,
            "previous_sql": sql_query,
            "sql_generation_error": None,
            "sql_generation_attempts": generation_attempts + 1,
            "sql_execution_result": None,
            "progress_tokens": [
                f"**Generated SQL:**\n```sql\n{sql_query}\n```\n\n*Executing...*\n\n"
            ],
        }
    except Exception as exc:
        print(f"[SQL Generation] Attempt {generation_attempts + 1} exception: {exc}")
        sql_q = locals().get("sql_query", previous_sql)
        return {
            "generated_sql": sql_q,
            "sql_generation_error": str(exc),
            "sql_generation_attempts": generation_attempts + 1,
            "sql_execution_result": None,
        }
    finally:
        db.close()


async def sql_execution_node(state: AgentState) -> dict:
    if state.get("sql_generation_error"):
        return {"sql_execution_error": state["sql_generation_error"]}

    generated_sql = state.get("generated_sql")
    attempts = state["sql_execution_attempts"]

    db = get_db_session()
    try:
        connection_id = state["db_connection_id"]
        conn_uuid = (
            uuid.UUID(connection_id)
            if isinstance(connection_id, str)
            else connection_id
        )
        connection = (
            db.query(ExternalDatabaseConnection)
            .filter(ExternalDatabaseConnection.id == conn_uuid)
            .first()
        )

        schema_cache = (
            db.query(DatabaseSchemaCache)
            .filter(DatabaseSchemaCache.connection_id == conn_uuid)
            .first()
        )
        schema_cache_tables = (
            schema_cache.schema_data.get("tables", [])
            if schema_cache and schema_cache.schema_data
            else []
        )

        start_time = time.perf_counter()
        query_results = database_service.run_query_on_connection(
            connection=connection,
            sql_query=generated_sql,
            schema_cache_tables=schema_cache_tables,
        )
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        print(f"[SQL Execution] Attempt {attempts + 1}, rows: {len(query_results)}")

        return {
            "sql_execution_result": query_results,
            "sql_execution_error": None,
            "sql_execution_attempts": attempts + 1,
            "sql_result": SQLAgentResult(
                success=True,
                sql_query=generated_sql,
                query_results=query_results,
                formatted_results=json.dumps(query_results, indent=2, default=str),
                connection_name=state.get("db_connection_name"),
                connection_id=state.get("db_connection_id"),
                execution_time_ms=execution_time_ms,
                attempts=state["sql_generation_attempts"],
            ),
        }
    except Exception as exc:
        print(f"[SQL Execution] Attempt {attempts + 1} exception: {exc}")
        return {
            "sql_execution_result": None,
            "sql_execution_error": str(exc),
            "sql_execution_attempts": attempts + 1,
            "sql_generation_error": str(exc),
            "sql_result": SQLAgentResult(success=False, error=str(exc)),
        }
    finally:
        db.close()


async def sql_result_judge_node(state: AgentState) -> dict:
    if state.get("context_error"):
        return {}

    sql_result = state.get("sql_result")
    if not sql_result or not sql_result.success:
        return {
            "sql_sufficient": False,
            "sql_judge_reasoning": sql_result.error
            if sql_result
            else "SQL execution failed.",
            "sql_fix_instruction": "",
            "sql_result_attempts": state["sql_result_attempts"] + 1,
        }

    query_plan = state.get("query_plan") or {}
    query_goal = query_plan.get("goal") or state["query"]

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
            query=query_goal,
            sql_query=sql_result.sql_query,
            query_results=query_results,
        )

    print(
        f"[SQL Judge] sufficient={judgment['sufficient']}, confidence={judgment['confidence']}"
    )
    print(f"[SQL Judge] reasoning: {judgment['reasoning']}")

    updated_dict = {**sql_result.__dict__}
    updated_dict["confidence"] = judgment["confidence"]
    updated_dict["reasoning"] = judgment["reasoning"]

    return {
        "sql_sufficient": judgment["sufficient"],
        "sql_judge_reasoning": judgment["reasoning"],
        "sql_fix_instruction": judgment.get("fix_instruction", ""),
        "sql_result": SQLAgentResult(**updated_dict),
        "sql_result_attempts": state["sql_result_attempts"] + 1,
    }
