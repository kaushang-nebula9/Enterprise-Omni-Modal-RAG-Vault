"""
RAG (Retrieval-Augmented Generation) service.

Handles:
  - Excel query execution in a RestrictedPython sandbox
  - Full RAG pipeline: embed query → Qdrant search → Excel pipeline → LLM answer

"""

import asyncio
import logging
import threading
import uuid
from typing import Optional, AsyncGenerator

import pandas as pd
from RestrictedPython import compile_restricted, safe_globals
from sqlalchemy.orm import Session
from sqlalchemy import or_

from anthropic import Anthropic, AsyncAnthropic

from app.core.config import settings
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.enums import FileType, DocumentStatus
from app.models.user import User
from app.services import embedding_service
from app.services.qdrant_service import search_vectors
from app.services.storage_service import get_absolute_path
from app.models.external_database import ExternalDatabaseConnection, DatabaseSchemaCache
from app.services.database_service import (
    check_user_db_access,
    get_user_authorized_tables,
    translate_nl_to_sql,
    run_query_on_connection,
)
import json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic client (ACTIVE)
# ---------------------------------------------------------------------------

_anthropic_client: Anthropic | None = None
_async_anthropic_client: AsyncAnthropic | None = None


def _get_anthropic_client() -> Anthropic:
    """Lazily initialise and return the Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


def _get_async_anthropic_client() -> AsyncAnthropic:
    """Lazily initialise and return the AsyncAnthropic client."""
    global _async_anthropic_client
    if _async_anthropic_client is None:
        _async_anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _async_anthropic_client


# ---------------------------------------------------------------------------
# CrossEncoder model (ACTIVE)
# ---------------------------------------------------------------------------

_cross_encoder: Optional["CrossEncoder"] = None  # noqa: F821


def _get_cross_encoder() -> "CrossEncoder":  # noqa: F821
    """Lazily load and cache the CrossEncoder model."""
    global _cross_encoder
    if not settings.ENABLE_CROSS_ENCODER_RERANKING:
        raise RuntimeError("Cross-encoder re-ranking is disabled via config.")
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        logger.info("Loading CrossEncoder model: cross-encoder/ms-marco-MiniLM-L-6-v2")
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder


# ---------------------------------------------------------------------------
# Excel query execution
# ---------------------------------------------------------------------------

_EXCEL_CODE_PROMPT = """You have access to a pandas dataframe called `df` with the following schema:
Columns: {columns}
Dtypes: {dtypes}
Shape: {rows} rows, {cols} columns
Sample rows: {sample}

User question: {query}

Write a single pandas expression or a short pandas code block to answer this question accurately.
Rules:
- The dataframe is already loaded as `df`
- Do not import any libraries
- Do not use any file I/O operations
- ALWAYS check if a filtered dataframe is empty before accessing `.iloc[0]` or `.index[0]` to avoid IndexErrors. If it is empty, set result to None or an appropriate message.
- Assign the final result to a variable called `result`
- Return only the code, no explanation, no markdown, no backticks"""


def execute_excel_query(
    file_path: str,
    schema: dict,
    query: str,
) -> Optional[str]:
    """
    Generate a pandas query via Claude and execute it in a RestrictedPython
    sandbox with a 10-second timeout.

    Returns str(result) on success, None on any failure.
    """
    try:
        # Load the dataframe
        df = pd.read_excel(file_path, engine="openpyxl")

        # Build the prompt
        prompt = _EXCEL_CODE_PROMPT.format(
            columns=schema.get("columns", []),
            dtypes=schema.get("dtypes", {}),
            rows=schema.get("shape", {}).get("rows", 0),
            cols=schema.get("shape", {}).get("columns", 0),
            sample=schema.get("sample", []),
            query=query,
        )

        # -- Anthropic LLM call (ACTIVE) ------------------------------------------
        client = _get_anthropic_client()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        code = (message.content[0].text or "").strip()

        # Strip markdown fences if present
        if code.startswith("```"):
            code = code.split("\n", 1)[-1]
            if code.endswith("```"):
                code = code[: -len("```")].strip()

        if not code:
            logger.warning("Anthropic returned empty code for Excel query")
            return None

        # Compile with RestrictedPython
        compiled = compile_restricted(code, filename="<excel_query>", mode="exec")

        # Build restricted globals — only allow df and safe builtins
        from RestrictedPython.Guards import guarded_iter_unpack_sequence
        from RestrictedPython.Eval import (
            default_guarded_getitem,
            default_guarded_getiter,
        )

        restricted_globals = dict(safe_globals)
        restricted_globals["_getattr_"] = getattr
        restricted_globals["_getitem_"] = default_guarded_getitem
        restricted_globals["_getiter_"] = default_guarded_getiter
        restricted_globals["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence

        # We use a pass-through write guard because full_write_guard wraps the object
        # and breaks Pandas dataframe item assignments (df['a'] = 1)
        restricted_globals["_write_"] = lambda x: x
        restricted_globals["pd"] = pd

        restricted_locals: dict = {"df": df}

        # Execution with a 10-second timeout (threading approach for Windows)
        result_container: dict = {"result": None, "error": None}

        def _execute():
            try:
                exec(compiled, restricted_globals, restricted_locals)  # noqa: S102
                result_container["result"] = restricted_locals.get("result")
            except Exception as exc:
                result_container["error"] = str(exc)

        thread = threading.Thread(target=_execute, daemon=True)
        thread.start()
        thread.join(timeout=10)

        if thread.is_alive():
            logger.warning("Excel query execution timed out (10s)")
            return None

        if result_container["error"]:
            logger.debug("Excel query execution error: %s", result_container["error"])
            return None

        result = result_container["result"]
        if result is None:
            return None

        return str(result)

    except Exception as exc:
        logger.error("execute_excel_query failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# RAG pipeline
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an intelligent assistant for an enterprise knowledge management system.
Answer the user's question based ONLY on the provided context below.
If the answer cannot be found in the context, say "I could not find relevant information in the available documents."
Do not make up information. Be concise and accurate.

At the very end of your response, after your answer, you MUST suggest 2-3 subsequent questions that the user may likely ask next. These questions must strictly be related to the provided context.
You MUST format this section exactly like this:
[FOLLOW_UP]
- Question 1?
- Question 2?
- Question 3?
"""


async def _rerank_chunks(query: str, hits: list[dict], label: str = "") -> list[dict]:
    """
    Re-ranks a list of Qdrant hits against the query using the CrossEncoder.
    Falls back to the original (RRF-ranked) order if re-ranking fails.
    """
    if not hits:
        return hits
    if not settings.ENABLE_CROSS_ENCODER_RERANKING:
        return hits
    try:
        model = _get_cross_encoder()
        pairs = [
            (query, hit.get("payload", {}).get("chunk_text") or "") for hit in hits
        ]
        scores = await asyncio.to_thread(model.predict, pairs)
        for hit, score in zip(hits, scores):
            hit["cross_encoder_score"] = float(score)
        hits.sort(key=lambda x: x.get("cross_encoder_score", -999999.0), reverse=True)
    except Exception as exc:
        logger.error(
            "CrossEncoder re-ranking failed%s: %s",
            f" for {label}" if label else "",
            exc,
        )
        # Fall back to original RRF-ranked order (already the order in `hits`)
    return hits


def _format_chunk_context(filename: str, hit: dict) -> str:
    """Formats a single Qdrant hit into a context block line."""
    payload = hit.get("payload", {})
    page = payload.get("page_number")
    slide = payload.get("slide_number")
    chunk_idx = payload.get("chunk_index", 0)
    chunk_text = payload.get("chunk_text", "")

    location_parts = []
    if page is not None:
        location_parts.append(f"Page: {page}")
    if slide is not None:
        location_parts.append(f"Slide: {slide}")
    location = " | ".join(location_parts) if location_parts else ""
    location_str = f" | {location}" if location else ""

    return f"Source: {filename}{location_str} | Chunk: {chunk_idx}\n{chunk_text}"


async def _run_excel_query(doc: Document, query: str) -> Optional[dict]:
    """Runs an Excel code-gen query for a single document. Returns None on failure or no schema."""
    if not doc.excel_schema:
        return None
    try:
        abs_path = get_absolute_path(doc.file_path)
        result = await asyncio.to_thread(
            execute_excel_query, abs_path, doc.excel_schema, query
        )
        if result is not None:
            return {
                "filename": doc.filename,
                "document_id": str(doc.id),
                "result": result,
            }
    except Exception as exc:
        logger.warning("Excel query failed for %s: %s", doc.filename, exc)
    return None


async def _run_qdrant_search(
    query: str,
    query_vector,
    collection_name: str,
    role_ids: list[str],
    document_id: Optional[str] = None,
    limit: int = 15,
) -> list[dict]:
    """Runs a Qdrant search, returning [] on failure rather than raising."""
    try:
        return await asyncio.to_thread(
            search_vectors,
            collection_name=collection_name,
            query_text=query,
            query_vector=query_vector,
            role_ids=role_ids,
            limit=limit,
            document_id=document_id,
        )
    except Exception as exc:
        logger.error(
            "Qdrant search failed%s: %s",
            f" for document {document_id}" if document_id else "",
            exc,
        )
        return []


async def _resolve_compare_document(
    did_uuid: uuid.UUID,
    query: str,
    query_vector,
    tenant_id: str,
    role_ids: list[str],
    compare_id_to_doc: dict[str, Document],
    all_authorized_docs: list[Document],
) -> tuple[str, list[str]]:
    """
    Resolves the context lines for a single document in /compare mode.
    Returns (context_text, [the qdrant hits contributed, if any]) so the caller
    can both build the context block and collect citations.
    """
    did_str = str(did_uuid)
    doc_in_db = compare_id_to_doc.get(did_str)

    if not doc_in_db:
        return (
            f"Source: Unknown Document ({did_str})\n[Note: This document was not found in the database.]",
            [],
        )

    filename = doc_in_db.filename
    authorized_doc = next(
        (d for d in all_authorized_docs if str(d.id) == did_str), None
    )

    if not authorized_doc:
        return (
            f"Source: {filename}\n[Note: This document has no available content or is still processing.]",
            [],
        )

    if authorized_doc.file_type == FileType.excel:
        if not authorized_doc.excel_schema:
            return (
                f"Source: {filename}\n[Note: This Excel document has no defined schema.]",
                [],
            )
        result = await _run_excel_query(authorized_doc, query)
        if result is not None:
            return f"Source: {filename}\nQuery: {query}\nResult: {result['result']}", []
        return (
            f"Source: {filename}\n[Note: No data results were retrieved from this Excel document.]",
            [],
        )

    # Non-Excel: Qdrant search scoped to this one document, then re-rank and keep top 6.
    collection_name = authorized_doc.qdrant_collection or f"tenant_{tenant_id}"
    doc_results = await _run_qdrant_search(
        query=query,
        query_vector=query_vector,
        collection_name=collection_name,
        role_ids=role_ids,
        document_id=did_str,
        limit=15,
    )
    doc_results = [
        hit
        for hit in doc_results
        if hit.get("payload", {}).get("document_id") == did_str
    ]
    doc_results = await _rerank_chunks(query, doc_results, label=filename)
    doc_results = doc_results[:6]

    if not doc_results:
        return (
            f"Source: {filename}\n[Note: This document has no ready or indexed chunks.]",
            [],
        )

    lines = [_format_chunk_context(filename, hit) for hit in doc_results]
    return "\n---\n".join(lines), doc_results


def is_value_mismatch_error(engine_type: str, e: Exception) -> bool:
    err_str = str(e).lower()
    orig = getattr(e, "orig", None)
    from app.models.enums import DatabaseEngine

    if engine_type == DatabaseEngine.postgresql:
        if orig and hasattr(orig, "pgcode") and orig.pgcode == "22P02":
            return True
        if "invalid input value for enum" in err_str:
            return True
        if "invalidtextrepresentation" in err_str:
            return True
        if "invalid input syntax for" in err_str:
            return True

    elif engine_type == DatabaseEngine.mysql:
        if (
            orig
            and hasattr(orig, "args")
            and isinstance(orig.args, tuple)
            and len(orig.args) > 0
        ):
            err_code = orig.args[0]
            if err_code in (1265, 1366, 1292):
                return True
        if "data truncated" in err_str:
            return True
        if "truncated incorrect" in err_str:
            return True
        if "incorrect integer value" in err_str:
            return True

    return False


def get_recent_turns(db: Session, session_id: uuid.UUID, limit: int = 5) -> list[dict]:
    from app.models.query_message import QueryMessage
    from app.models.enums import MessageRole

    messages = (
        db.query(QueryMessage)
        .filter(QueryMessage.session_id == session_id)
        .order_by(QueryMessage.created_at.desc())
        .limit(limit * 2)
        .all()
    )
    messages = list(reversed(messages))

    turns = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.role == MessageRole.user:
            if i + 1 < len(messages) and messages[i + 1].role == MessageRole.assistant:
                turns.append(
                    {
                        "question": msg.content,
                        "answer": messages[i + 1].content,
                        "generated_sql": getattr(
                            messages[i + 1], "generated_sql", None
                        ),
                        "query_results": getattr(
                            messages[i + 1], "query_results", None
                        ),
                    }
                )
                i += 2
            else:
                i += 1
        else:
            i += 1

    return turns[-limit:]


async def run_rag_pipeline(
    query: str,
    user: User,
    db: Session,
    conversation_history: str = "",
    document_id: Optional[uuid.UUID] = None,
    database_id: Optional[uuid.UUID] = None,
    command_instruction: Optional[str] = None,
    compare_document_ids: Optional[list[uuid.UUID]] = None,
    is_compare_mode: bool = False,
    is_summarize_mode: bool = False,
    model_id: Optional[uuid.UUID] = None,
    session_id: Optional[uuid.UUID] = None,
) -> AsyncGenerator[dict, None]:
    """
    Main RAG pipeline with streaming output:
      1. Embed the user query
      2. Fetch authorised documents
      3. Qdrant semantic search (non-Excel) / Excel code-gen pipeline (run concurrently)
      4. Build context
      5. Use Claude to stream response
      6. Yield tokens and final citations
    """
    if database_id:
        connection = (
            db.query(ExternalDatabaseConnection)
            .filter(
                ExternalDatabaseConnection.id == database_id,
                ExternalDatabaseConnection.tenant_id == user.tenant_id,
            )
            .first()
        )
        if not connection:
            yield {"type": "token", "content": "Error: Database connection not found."}
            yield {
                "type": "done",
                "answer": "Error: Database connection not found.",
                "citations": [],
                "follow_up_questions": [],
            }
            return

        if not check_user_db_access(db, user, database_id):
            yield {
                "type": "token",
                "content": "Error: You do not have permission to access this database.",
            }
            yield {
                "type": "done",
                "answer": "Error: Access denied.",
                "citations": [],
                "follow_up_questions": [],
            }
            return

        schema_cache = (
            db.query(DatabaseSchemaCache)
            .filter(DatabaseSchemaCache.connection_id == database_id)
            .first()
        )
        if not schema_cache or not schema_cache.schema_data:
            yield {
                "type": "token",
                "content": "Error: Database schema has not been introspected yet. Please contact your administrator.",
            }
            yield {
                "type": "done",
                "answer": "Error: Schema missing.",
                "citations": [],
                "follow_up_questions": [],
            }
            return

        all_tables = [t["name"] for t in schema_cache.schema_data.get("tables", [])]
        authorized_table_names = get_user_authorized_tables(
            db, user, database_id, all_tables
        )
        if not authorized_table_names:
            yield {
                "type": "token",
                "content": "Error: You do not have access to any tables in this database.",
            }
            yield {
                "type": "done",
                "answer": "Error: Table access denied.",
                "citations": [],
                "follow_up_questions": [],
            }
            return

        from app.models.external_database import DatabaseAccessPolicy
        from app.services.database_service import (
            get_user_authorized_columns_for_table,
            check_sql_authorized_columns,
        )

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
                    # Filter columns shown to the LLM to only the ones authorized
                    tbl_copy["columns"] = [
                        col
                        for col in t.get("columns", [])
                        if col["name"].lower() in auth_cols
                    ]
                    authorized_tables_info.append(tbl_copy)

        if not authorized_tables_info:
            yield {
                "type": "token",
                "content": "Error: You do not have access to any columns/tables in this database.",
            }
            yield {
                "type": "done",
                "answer": "Error: Table access denied.",
                "citations": [],
                "follow_up_questions": [],
            }
            return

        filtered_schema_data = {"tables": authorized_tables_info}

        yield {
            "type": "token",
            "content": "*Thinking... Translating your request to SQL...*\n\n",
        }
        turns = []
        if session_id:
            turns = get_recent_turns(db, session_id, settings.SQL_HISTORY_LIMIT)

        try:
            sql_query = await translate_nl_to_sql(
                query=query,
                schema_data_filtered=filtered_schema_data,
                engine_type=connection.engine,
                db=db,
                model_id=model_id,
                conversation_history=turns,
                user_id=user.id,
                tenant_id=user.tenant_id,
            )

            # Enforce guardrails on generated SQL
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
                "content": f"**Generated SQL Query:**\n```sql\n{sql_query}\n```\n\n*Executing query...*\n\n",
            }
        except Exception as e:
            err_msg = str(e)
            if "I cannot generate a SQL query, this is ambiguous" in err_msg:
                err_msg = "I cannot generate a SQL query, this is ambiguous"
            else:
                err_msg = f"Error during SQL generation: {str(e)}"
            yield {"type": "token", "content": err_msg}
            yield {
                "type": "done",
                "answer": err_msg,
                "citations": [],
                "follow_up_questions": [],
            }
            return

        try:
            query_results = run_query_on_connection(
                connection=connection,
                sql_query=sql_query,
                schema_cache_tables=schema_cache.schema_data.get("tables", []),
            )
        except Exception as e:
            if is_value_mismatch_error(connection.engine, e):
                # Log retry event
                logger.warning(
                    f"Connection {connection.id} - NL-to-SQL execution failed with value/literal mismatch: {str(e)}. "
                    f"Original SQL: {sql_query}. Attempting self-correction..."
                )
                yield {
                    "type": "token",
                    "content": f"\n*Database reported a value/literal mismatch error: {str(e)}.*\n*Attempting self-correction (retry 1/1)...*\n\n",
                }

                try:
                    # Regenerate SQL with error feedback
                    sql_query = await translate_nl_to_sql(
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

                    # Enforce guardrails on regenerated SQL
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

                    # Re-run execution and re-verify
                    query_results = run_query_on_connection(
                        connection=connection,
                        sql_query=sql_query,
                        schema_cache_tables=schema_cache.schema_data.get("tables", []),
                    )

                    # Log successful retry
                    logger.info(
                        f"Connection {connection.id} - NL-to-SQL self-correction successful. New SQL: {sql_query}"
                    )

                except Exception as retry_err:
                    # Log failed retry
                    logger.error(
                        f"Connection {connection.id} - NL-to-SQL self-correction failed. "
                        f"Regenerated SQL: {sql_query}. Error: {str(retry_err)}"
                    )
                    err_msg = str(retry_err)
                    if "I cannot generate a SQL query, this is ambiguous" in err_msg:
                        err_msg = "I cannot generate a SQL query, this is ambiguous"
                    else:
                        err_msg = f"Error executing query: {str(retry_err)}"
                    yield {"type": "token", "content": err_msg}
                    yield {
                        "type": "done",
                        "answer": err_msg,
                        "citations": [],
                        "follow_up_questions": [],
                    }
                    return
            else:
                err_msg = str(e)
                if "I cannot generate a SQL query, this is ambiguous" in err_msg:
                    err_msg = "I cannot generate a SQL query, this is ambiguous"
                else:
                    err_msg = f"Error executing query: {str(e)}"
                yield {"type": "token", "content": err_msg}
                yield {
                    "type": "done",
                    "answer": err_msg,
                    "citations": [],
                    "follow_up_questions": [],
                }
                return

        formatted_results_str = json.dumps(query_results, indent=2, default=str)

        system_prompt = (
            "You are a helpful data analyst assistant. Your job is to analyze the executed SQL query and its returned results, "
            "and provide a clear, concise, and professional natural language answer to the user's original question. "
            "Make sure to format the output nicely (e.g. use markdown tables or bullet points where appropriate). "
            "Always cite values directly from the query results. If the results are empty, explain that no matching records were found."
        )

        prompt = f"""User Question: {query}
Generated SQL Query: {sql_query}
Query Results:
{formatted_results_str}

Please summarize and answer the user's question based on the query results. Do not make up any facts."""

        selected_model_string = "claude-haiku-4-5-20251001"
        selected_provider = "anthropic"

        if model_id:
            from app.models.available_model import AvailableModel

            db_model = (
                db.query(AvailableModel).filter(AvailableModel.id == model_id).first()
            )
            if db_model:
                selected_model_string = db_model.model_string
                selected_provider = db_model.provider

        input_tokens = 0
        output_tokens = 0

        full_answer_list = []
        if selected_provider == "anthropic":
            client = _get_async_anthropic_client()
            async with client.messages.stream(
                model=selected_model_string,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        full_answer_list.append(event.text)
                        yield {"type": "token", "content": event.text}

                final_msg = await stream.get_final_message()
                if getattr(final_msg, "usage", None):
                    input_tokens = getattr(final_msg.usage, "input_tokens", 0)
                    output_tokens = getattr(final_msg.usage, "output_tokens", 0)
        elif selected_provider == "openrouter":
            from app.services.openrouter_service import stream_openrouter_completion

            async for chunk_type, data in stream_openrouter_completion(
                model_string=selected_model_string,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            ):
                if chunk_type == "text":
                    full_answer_list.append(data)
                    yield {"type": "token", "content": data}
                elif chunk_type == "usage":
                    input_tokens = data.get("prompt_tokens", 0)
                    output_tokens = data.get("completion_tokens", 0)

        # Save SQL summarization UsageLog row
        try:
            from app.models.usage_log import UsageLog

            usage_log = UsageLog(
                tenant_id=user.tenant_id,
                user_id=user.id,
                provider=selected_provider.value
                if hasattr(selected_provider, "value")
                else selected_provider,
                model_string=selected_model_string,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            db.add(usage_log)
            db.commit()

            # Trigger budget check task in background
            try:
                import sys

                if "pytest" not in sys.modules:
                    from app.tasks.billing_tasks import check_tenant_budgets_task

                    check_tenant_budgets_task.delay()
            except Exception as task_exc:
                logger.error(
                    "Failed to trigger check_tenant_budgets_task: %s", task_exc
                )
        except Exception as usage_err:
            logger.error(f"Failed to save SQL summarization usage log: {usage_err}")

        full_answer = "".join(full_answer_list).strip()

        citations = [
            {
                "document_id": str(database_id),
                "filename": f"Database: {connection.name}",
                "chunk_text": f"SQL: {sql_query}\nResults: {formatted_results_str[:1000]}...",
                "page_number": None,
                "slide_number": None,
                "chunk_index": 0,
            }
        ]

        # Ensure query_results is JSON serializable (converts UUIDs, datetimes, etc. to strings)
        serializable_results = None
        if query_results is not None:
            serializable_results = json.loads(json.dumps(query_results, default=str))

        yield {
            "type": "done",
            "answer": full_answer,
            "citations": citations,
            "model_string": selected_model_string,
            "follow_up_questions": [],
            "generated_sql": sql_query,
            "query_results": serializable_results,
        }
        return

    tenant_id = str(user.tenant_id)
    role_id = str(user.role_id)
    search_role_ids = [role_id, str(user.id)]

    # Embed the query
    query_vector = embedding_service.embed_text(query)

    # Fetch documents accessible via role-based access policies or uploaded by the user
    docs_query = (
        db.query(Document)
        .outerjoin(
            DocumentAccessPolicy, Document.id == DocumentAccessPolicy.document_id
        )
        .filter(
            Document.tenant_id == user.tenant_id,
            Document.status == DocumentStatus.ready,
            or_(
                DocumentAccessPolicy.role_id == user.role_id,
                Document.uploaded_by == user.id,
            ),
        )
    )

    if compare_document_ids:
        docs_query = docs_query.filter(Document.id.in_(compare_document_ids))
    elif document_id:
        docs_query = docs_query.filter(Document.id == document_id)

    all_authorized_docs = docs_query.distinct().all()

    excel_docs = [d for d in all_authorized_docs if d.file_type == FileType.excel]
    non_excel_exist = any(d.file_type != FileType.excel for d in all_authorized_docs)

    # Build a lookup of document_id -> filename
    doc_id_to_filename: dict[str, str] = {
        str(doc.id): doc.filename for doc in all_authorized_docs
    }

    context_parts: list[str] = []
    qdrant_results: list[dict] = []

    if is_compare_mode and compare_document_ids:
        compare_docs_db = (
            db.query(Document).filter(Document.id.in_(compare_document_ids)).all()
        )
        compare_id_to_doc = {str(d.id): d for d in compare_docs_db}

        # Make sure compare docs are in doc_id_to_filename so citation lookups work
        for did_str, doc in compare_id_to_doc.items():
            doc_id_to_filename.setdefault(did_str, doc.filename)

        # Resolve each document in the compare set concurrently (preserves order via gather).
        resolutions = await asyncio.gather(
            *[
                _resolve_compare_document(
                    did_uuid,
                    query,
                    query_vector,
                    tenant_id,
                    search_role_ids,
                    compare_id_to_doc,
                    all_authorized_docs,
                )
                for did_uuid in compare_document_ids
            ],
            return_exceptions=True,
        )

        for did_uuid, resolution in zip(compare_document_ids, resolutions):
            if isinstance(resolution, BaseException):
                logger.error(
                    "Compare resolution failed for document %s: %s",
                    did_uuid,
                    resolution,
                )
                context_parts.append(
                    f"Source: Unknown Document ({did_uuid})\n[Note: Failed to retrieve content for this document.]"
                )
                context_parts.append("---")
                continue
            context_text, contributed_hits = resolution
            context_parts.append(context_text)
            context_parts.append("---")
            qdrant_results.extend(contributed_hits)

        context_block = (
            "\n".join(context_parts) if context_parts else "No relevant context found."
        )

    else:
        # Standard search/retrieval path: run Qdrant search and Excel pipeline concurrently.
        coroutines = []
        branches = []
        excel_results: list[dict] = []

        if non_excel_exist:
            collection_name = (
                all_authorized_docs[0].qdrant_collection
                if document_id and all_authorized_docs
                else f"tenant_{tenant_id}"
            )
            coroutines.append(
                _run_qdrant_search(
                    query=query,
                    query_vector=query_vector,
                    collection_name=collection_name,
                    role_ids=search_role_ids,
                    document_id=str(document_id) if document_id else None,
                    limit=15,
                )
            )
            branches.append("qdrant")

        excel_docs_to_run = [doc for doc in excel_docs if doc.excel_schema]
        if excel_docs_to_run:

            async def run_excel():
                sub_results = await asyncio.gather(
                    *[_run_excel_query(doc, query) for doc in excel_docs_to_run]
                )
                return [r for r in sub_results if r is not None]

            coroutines.append(run_excel())
            branches.append("excel")

        if coroutines:
            results = await asyncio.gather(*coroutines, return_exceptions=True)
            for branch, result in zip(branches, results):
                if isinstance(result, BaseException):
                    logger.error("%s branch failed with exception: %s", branch, result)
                    result = []
                if branch == "qdrant":
                    qdrant_results = result
                elif branch == "excel":
                    excel_results = result

        # Filter out any orphaned Qdrant vectors (e.g. from deleted documents)
        qdrant_results = [
            hit
            for hit in qdrant_results
            if hit.get("payload", {}).get("document_id") in doc_id_to_filename
        ]

        qdrant_results = await _rerank_chunks(query, qdrant_results)

        # Truncate candidates: allow more chunks (8) for summarize mode
        final_limit = 8 if (is_summarize_mode and document_id) else 5
        qdrant_results = qdrant_results[:final_limit]

        if qdrant_results:
            context_parts.append("[Document Chunks]")
            for hit in qdrant_results:
                filename = doc_id_to_filename.get(
                    hit.get("payload", {}).get("document_id", ""), "Unknown"
                )
                context_parts.append(_format_chunk_context(filename, hit))
                context_parts.append("---")

        if excel_results:
            context_parts.append("[Excel Data Results]")
            for er in excel_results:
                context_parts.append(
                    f"Source: {er['filename']}\nQuery: {query}\nResult: {er['result']}"
                )
                context_parts.append("---")

        context_block = (
            "\n".join(context_parts) if context_parts else "No relevant context found."
        )

    # Call LLM for the final answer (using Anthropic Claude Streaming)
    final_prompt = f"""Context:
    {context_block}

    Conversation History (recent messages):
    {conversation_history if conversation_history else "No previous messages."}

    User Question: {query}

    Answer:"""

    system_prompt = _SYSTEM_PROMPT
    if command_instruction:
        system_prompt += f"\n\n[Instructions]\n{command_instruction}"

    # Resolve model and provider
    selected_model_string = "claude-haiku-4-5-20251001"
    selected_provider = "anthropic"

    if model_id:
        from app.models.available_model import AvailableModel

        db_model = (
            db.query(AvailableModel).filter(AvailableModel.id == model_id).first()
        )
        if db_model:
            selected_model_string = db_model.model_string
            selected_provider = db_model.provider

    full_answer_list = []
    input_tokens = 0
    output_tokens = 0
    try:
        if selected_provider == "anthropic":
            client = _get_async_anthropic_client()
            stream_kwargs = {
                "model": selected_model_string,
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": [{"role": "user", "content": final_prompt}],
            }
            # Omit temperature if model is Opus (deprecated)
            if "opus" not in selected_model_string.lower():
                stream_kwargs["temperature"] = 0

            async with client.messages.stream(**stream_kwargs) as stream:
                async for event in stream:
                    if event.type == "text":
                        full_answer_list.append(event.text)
                        yield {"type": "token", "content": event.text}

                final_msg = await stream.get_final_message()
                if getattr(final_msg, "usage", None):
                    input_tokens = getattr(final_msg.usage, "input_tokens", 0)
                    output_tokens = getattr(final_msg.usage, "output_tokens", 0)
        elif selected_provider == "openrouter":
            from app.services.openrouter_service import stream_openrouter_completion

            async for chunk_type, data in stream_openrouter_completion(
                model_string=selected_model_string,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": final_prompt}],
            ):
                if chunk_type == "text":
                    full_answer_list.append(data)
                    yield {"type": "token", "content": data}
                elif chunk_type == "usage":
                    input_tokens = data.get("prompt_tokens", 0)
                    output_tokens = data.get("completion_tokens", 0)
        else:
            raise ValueError(f"Unsupported model provider: {selected_provider}")

        # Save UsageLog row
        try:
            from app.models.usage_log import UsageLog

            usage_log = UsageLog(
                tenant_id=user.tenant_id,
                user_id=user.id,
                provider=selected_provider,
                model_string=selected_model_string,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            db.add(usage_log)
            db.commit()

            # Trigger budget check task in background
            try:
                import sys

                if "pytest" not in sys.modules:
                    from app.tasks.billing_tasks import check_tenant_budgets_task

                    check_tenant_budgets_task.delay()
            except Exception as task_exc:
                logger.error(
                    "Failed to trigger check_tenant_budgets_task: %s", task_exc
                )
        except Exception as db_exc:
            logger.error("Failed to save usage log to database: %s", db_exc)
            db.rollback()
    except Exception as exc:
        logger.error(
            "%s streaming answer generation failed: %s", selected_provider, exc
        )
        error_msg = (
            "I encountered an error while generating an answer. Please try again."
        )
        full_answer_list.append(error_msg)
        yield {"type": "token", "content": error_msg}

    full_answer = "".join(full_answer_list).strip()
    if not full_answer:
        full_answer = (
            "I could not generate an answer. Please try rephrasing your question."
        )
        yield {"type": "token", "content": full_answer}

    # Parse follow up questions using regex split
    import re

    answer_parts = re.split(r"(?i)\[follow[-_]up\]", full_answer)
    clean_answer = answer_parts[0].strip()
    follow_up_questions: list[str] = []
    if len(answer_parts) > 1:
        raw_questions = answer_parts[1].strip().split("\n")
        for q in raw_questions:
            q = q.strip().lstrip("-").lstrip("*").lstrip("123456789.").strip()
            if q:
                follow_up_questions.append(q)

    # Build citations list
    citations: list[dict] = []
    for hit in qdrant_results:
        payload = hit.get("payload", {})
        doc_id = payload.get("document_id", "")
        citations.append(
            {
                "document_id": doc_id,
                "filename": doc_id_to_filename.get(doc_id, "Unknown"),
                "chunk_text": payload.get("chunk_text", ""),
                "page_number": payload.get("page_number"),
                "slide_number": payload.get("slide_number"),
                "chunk_index": payload.get("chunk_index", 0),
            }
        )

    yield {
        "type": "done",
        "answer": clean_answer,
        "citations": citations,
        "model_string": selected_model_string,
        "follow_up_questions": follow_up_questions,
    }
