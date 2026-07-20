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
from sentence_transformers import CrossEncoder
from sqlalchemy.orm import Session

from anthropic import Anthropic, AsyncAnthropic

from app.core.config import settings
from app.models.document import Document
from app.models.enums import (
    FileType,
    EXTENSION_TO_FILE_TYPE,
    TABULAR_FILE_TYPES,
)
from app.services.document_processor import load_dataframe
from app.models.user import User
from app.services.qdrant_service import search_vectors
from app.services.storage_service import get_absolute_path
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

_cross_encoder: Optional["CrossEncoder"] = None


def _get_cross_encoder() -> "CrossEncoder":
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
    file_type: Optional[FileType] = None,
) -> Optional[str]:
    """
    Generate a pandas query via Claude and execute it in a RestrictedPython
    sandbox with a 10-second timeout.

    Returns str(result) on success, None on any failure.
    """
    try:
        print(
            f"Executing Excel query for {file_path} with schema: {json.dumps(schema)} and query: {query}"
        )
        # Load the dataframe
        if file_type is None:
            ext = "." + file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
            file_type = EXTENSION_TO_FILE_TYPE.get(ext)
            if not file_type:
                raise ValueError(f"Unsupported file extension: {ext}")
        df = load_dataframe(file_path, file_type)

        print(
            f"Loaded dataframe with shape: {df.shape} and columns: {df.columns.tolist()}"
        )
        # Build the prompt
        prompt = _EXCEL_CODE_PROMPT.format(
            columns=schema.get("columns", []),
            dtypes=schema.get("dtypes", {}),
            rows=schema.get("shape", {}).get("rows", 0),
            cols=schema.get("shape", {}).get("columns", 0),
            sample=schema.get("sample", []),
            query=query,
        )
        print(f"Generated prompt for Claude: {prompt}")

        # -- Anthropic LLM call (ACTIVE) ------------------------------------------
        client = _get_anthropic_client()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        code = (message.content[0].text or "").strip()

        print(f"Received code from Claude: {code}")

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
        print(f"Compiled code: {compiled}")
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
        print(f"Excel query execution result: {result}")
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

CHART OUTPUT RULE:
If and only if your answer contains numerical data that can be meaningfully visualised (comparisons, trends, distributions, rankings, time series), append a chart specification at the very end of your response using this exact format:

CHART_SPEC:{"chart_type":"bar","title":"<descriptive title>","x_key":"<field name>","y_keys":["<field name>"],"data":[{...},{...}]}

Rules for the chart spec:
- chart_type must be one of: bar, line, area, pie
- Choose the most appropriate chart_type for the data
- data must be a JSON array of flat objects, all objects must have the same keys
- x_key is the categorical or time-based field
- y_keys is an array of one or more numeric fields
- For pie charts, y_keys must contain exactly one field
- All values in y_keys fields must be numbers, not strings
- The CHART_SPEC line must be on its own line at the very end of your response, after all text
- Do not emit CHART_SPEC if the answer is narrative, qualitative, or contains no numerical comparisons
- Do not wrap CHART_SPEC in markdown code fences
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
            execute_excel_query, abs_path, doc.excel_schema, query, doc.file_type
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

    if authorized_doc.file_type in TABULAR_FILE_TYPES:
        if not authorized_doc.excel_schema:
            return (
                f"Source: {filename}\n[Note: This document has no defined schema.]",
                [],
            )
        result = await _run_excel_query(authorized_doc, query)
        if result is not None:
            return f"Source: {filename}\nQuery: {query}\nResult: {result['result']}", []
        return (
            f"Source: {filename}\n[Note: No data results were retrieved from this document.]",
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


async def _execute_llm_stream(cfg, sys_prompt, user_prompt, max_tokens=8192):
    """
    Streams tokens and usage dict from the appropriate provider SDK based on configuration.
    """
    from app.core.utils import get_provider_by_id, get_llm_client

    cfg_provider_id = cfg.provider_id
    cfg_model_string = cfg.model_name or cfg.model_string
    cfg_provider = get_provider_by_id(cfg_provider_id)
    cfg_sdk_type = cfg_provider["sdk_type"]

    if cfg_provider_id == "anthropic":
        if cfg.api_key:
            client = get_llm_client(cfg)
        else:
            client = _get_async_anthropic_client()

        stream_kwargs = {
            "model": cfg_model_string,
            "max_tokens": max_tokens,
            "system": sys_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if "opus" not in cfg_model_string.lower():
            stream_kwargs["temperature"] = 0

        async with client.messages.stream(**stream_kwargs) as stream:
            async for event in stream:
                if event.type == "text":
                    yield "token", event.text
            final_msg = await stream.get_final_message()
            if getattr(final_msg, "usage", None):
                yield (
                    "usage",
                    {
                        "input_tokens": getattr(final_msg.usage, "input_tokens", 0),
                        "output_tokens": getattr(final_msg.usage, "output_tokens", 0),
                    },
                )

    elif cfg_provider_id == "openrouter":
        from app.services.openrouter_service import stream_openrouter_completion

        async for chunk_type, data in stream_openrouter_completion(
            model_string=cfg_model_string,
            system_prompt=sys_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ):
            if chunk_type == "text":
                yield "token", data
            elif chunk_type == "usage":
                yield (
                    "usage",
                    {
                        "input_tokens": data.get("prompt_tokens", 0),
                        "output_tokens": data.get("completion_tokens", 0),
                    },
                )

    elif cfg_sdk_type == "openai_compat":
        client = get_llm_client(cfg)
        formatted_messages = []
        if sys_prompt:
            formatted_messages.append({"role": "system", "content": sys_prompt})
        formatted_messages.append({"role": "user", "content": user_prompt})

        response = await client.chat.completions.create(
            model=cfg_model_string,
            messages=formatted_messages,
            temperature=0,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in response:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    yield "token", delta.content
            if getattr(chunk, "usage", None) and chunk.usage:
                yield (
                    "usage",
                    {
                        "input_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                        "output_tokens": getattr(chunk.usage, "completion_tokens", 0),
                    },
                )

    elif cfg_sdk_type == "google":
        client = get_llm_client(cfg)
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=sys_prompt,
            temperature=0,
            max_output_tokens=max_tokens,
        )
        response_stream = await client.aio.models.generate_content_stream(
            model=cfg_model_string,
            contents=user_prompt,
            config=config,
        )
        async for chunk in response_stream:
            text = chunk.text
            if text:
                yield "token", text
            if chunk.usage_metadata:
                yield (
                    "usage",
                    {
                        "input_tokens": chunk.usage_metadata.prompt_token_count or 0,
                        "output_tokens": chunk.usage_metadata.candidates_token_count
                        or 0,
                    },
                )
    else:
        raise ValueError(f"Unsupported sdk_type: {cfg_sdk_type}")


def is_cross_source_query(query: str) -> bool:
    """
    Heuristic to detect whether a query requires results from both
    a database and a document/file source simultaneously.
    """
    q = query.lower()
    doc_terms = {
        "document",
        "file",
        "csv",
        "spreadsheet",
        "report",
        "attachment",
        "uploaded",
    }
    db_terms = {"database", "db", "table", "sql", "query", "record", "records"}
    compare_terms = {
        "compare",
        "comparison",
        "contrast",
        "difference",
        "different",
        "vs",
        "versus",
        "both",
        "also in",
        "same in",
        "match",
        "matches",
        "how does",
        "how do",
        "differ",
        "unlike",
        "similar",
        "similarity",
    }
    has_compare = any(t in q for t in compare_terms)
    has_doc = any(t in q for t in doc_terms)
    has_db = any(t in q for t in db_terms)
    return has_compare or (has_doc and has_db)


async def _resolve_model_config(
    model_id,
    db,
    user,
    query: str = "",
    context_chunks: list[str] = None,
    has_attachments: bool = False,
):
    """
    Resolves model_id to (selected_model_string, selected_provider_id, model_config, db_model).
    Falls back to claude-haiku-4-5 / anthropic if nothing is resolved.
    """
    selected_model_string = "claude-haiku-4-5"
    selected_provider_id = "anthropic"
    model_config = None
    db_model = None

    if model_id:
        from app.models.available_model import AvailableModel

        if str(model_id) == "auto":
            db_models = (
                db.query(AvailableModel)
                .filter(
                    AvailableModel.is_active,
                    (AvailableModel.tenant_id == user.tenant_id)
                    | (AvailableModel.tenant_id.is_(None)),
                )
                .all()
            )
            available_models_list = [
                {
                    "id": m.id,
                    "display_name": m.display_name,
                    "model_name": m.model_name,
                    "tier": m.tier,
                    "provider_id": m.provider_id,
                    "base_url": m.base_url,
                    "api_key": m.api_key,
                    "is_default": m.is_default,
                }
                for m in db_models
            ]
            from app.services.model_router import route_model

            chosen_dict = route_model(
                query=query,
                context_chunks=context_chunks or [],
                has_attachments=has_attachments,
                available_models=available_models_list,
            )
            db_model = next((m for m in db_models if m.id == chosen_dict["id"]), None)
        else:
            db_model = (
                db.query(AvailableModel).filter(AvailableModel.id == model_id).first()
            )

        if db_model:
            selected_model_string = db_model.model_name or db_model.model_string
            selected_provider_id = db_model.provider_id
            if not selected_provider_id:
                # Fallback for legacy models / tests
                provider_val = db_model.provider
                if hasattr(provider_val, "value"):
                    provider_val = provider_val.value
                if provider_val == "anthropic":
                    selected_provider_id = "anthropic"
                elif provider_val == "openrouter":
                    selected_provider_id = "openrouter"
                else:
                    selected_provider_id = "openai_compat"
            model_config = db_model
            model_config.provider_id = selected_provider_id
            model_id = db_model.id

    if not model_config:
        from app.models.available_model import AvailableModel

        model_config = AvailableModel(
            provider_id=selected_provider_id,
            model_name=selected_model_string,
            api_key="",
        )
    return selected_model_string, selected_provider_id, model_config, db_model


async def _stream_llm_response(
    model_config,
    default_model,
    system_prompt: str,
    prompt: str,
    max_tokens: int,
    db,
    user,
) -> AsyncGenerator[dict, None]:
    """
    Calls the LLM with fallback, streams tokens as {"type": "token", "content": ...} dicts,
    saves a UsageLog row, triggers budget check, and finally yields a single
    {"type": "usage_done", "full_answer": ..., "was_fallback": ..., "fallback_model_name": ...,
     "db_model": ..., "model_string": ..., "provider_id": ...} dict.
    """
    from app.core.utils import call_llm_with_fallback

    was_fallback = False
    fallback_model_name = None
    input_tokens = 0
    output_tokens = 0
    full_answer_list = []

    # Invoke LLM with fallback support
    stream_result, was_fallback, fallback_model_name = await call_llm_with_fallback(
        primary_model_config=model_config,
        default_model_config=default_model,
        call_fn=lambda cfg: _execute_llm_stream(
            cfg, system_prompt, prompt, max_tokens=max_tokens
        ),
    )

    if was_fallback and default_model:
        db_model = default_model
        model_config = default_model
        selected_model_string = default_model.model_name or default_model.model_string
        selected_provider_id = default_model.provider_id
    else:
        db_model = (
            model_config if getattr(model_config, "id", None) is not None else None
        )
        selected_model_string = model_config.model_name or model_config.model_string
        selected_provider_id = model_config.provider_id

    async for event_type, data in stream_result:
        if event_type == "token":
            full_answer_list.append(data)
            yield {"type": "token", "content": data}
        elif event_type == "usage":
            input_tokens = data["input_tokens"]
            output_tokens = data["output_tokens"]

    # Save UsageLog row
    try:
        from app.models.usage_log import UsageLog

        usage_log = UsageLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            provider=selected_provider_id,
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
            logger.error("Failed to trigger check_tenant_budgets_task: %s", task_exc)
    except Exception as db_exc:
        logger.error("Failed to save usage log to database: %s", db_exc)
        db.rollback()

    full_answer = "".join(full_answer_list).strip()

    yield {
        "type": "usage_done",
        "full_answer": full_answer,
        "was_fallback": was_fallback,
        "fallback_model_name": fallback_model_name,
        "db_model": db_model,
        "model_string": selected_model_string,
        "provider_id": selected_provider_id,
    }


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
    from app.services.agents.orchestrator import run_orchestrator

    async for event in run_orchestrator(
        query=query,
        user=user,
        db=db,
        conversation_history=conversation_history,
        document_id=document_id,
        database_id=database_id,
        command_instruction=command_instruction,
        compare_document_ids=compare_document_ids,
        is_compare_mode=is_compare_mode,
        is_summarize_mode=is_summarize_mode,
        model_id=model_id,
        session_id=session_id,
    ):
        yield event
