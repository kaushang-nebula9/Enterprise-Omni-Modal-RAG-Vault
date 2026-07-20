import re
import json
import logging
from typing import AsyncGenerator
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.agents.types import FusionInput
import app.services.rag_service as rag_service
from app.models.available_model import AvailableModel
from app.services.model_router import route_model, get_default_model_config

logger = logging.getLogger(__name__)


async def _resolve_model_config(
    model_id,
    db,
    user,
    query: str = "",
    context_chunks: list[str] = None,
    has_attachments: bool = False,
):
    print("[Fusion Agent] Resolving model config...")
    selected_model_string = "claude-haiku-4-5"
    selected_provider_id = "anthropic"
    model_config = None
    db_model = None

    if model_id:
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
        model_config = AvailableModel(
            provider_id=selected_provider_id,
            model_name=selected_model_string,
            api_key="",
        )
    print(
        f"[Fusion Agent] Model resolved: {selected_model_string} via {selected_provider_id}"
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
    from app.core.utils import call_llm_with_fallback

    print(f"[Fusion Agent] Calling LLM. Max tokens: {max_tokens}")
    was_fallback = False
    fallback_model_name = None
    input_tokens = 0
    output_tokens = 0
    full_answer_list = []

    stream_result, was_fallback, fallback_model_name = await call_llm_with_fallback(
        primary_model_config=model_config,
        default_model_config=default_model,
        call_fn=lambda cfg: rag_service._execute_llm_stream(
            cfg, system_prompt, prompt, max_tokens=max_tokens
        ),
    )

    if was_fallback:
        print(f"[Fusion Agent] Fallback model used: {fallback_model_name}")

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

    print("[Fusion Agent] LLM stream started.")
    async for event_type, data in stream_result:
        if event_type == "token":
            full_answer_list.append(data)
            yield {"type": "token", "content": data}
        elif event_type == "usage":
            input_tokens = data["input_tokens"]
            output_tokens = data["output_tokens"]

    print(
        f"[Fusion Agent] LLM stream complete. Tokens - input: {input_tokens}, output: {output_tokens}"
    )

    print("[Fusion Agent] Saving usage log...")
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


async def run_fusion_agent(
    fusion_input: FusionInput,
    user: User,
    db: Session,
) -> AsyncGenerator[dict, None]:
    print(f"[Fusion Agent] Starting. Mode: {fusion_input.mode}")
    default_model = get_default_model_config(db, user.tenant_id)

    if fusion_input.mode == "db_only":
        print(f"[Fusion Agent] Building prompt for mode: {fusion_input.mode}")
        sql_result = fusion_input.sql_result
        query_results = sql_result.query_results
        sql_query = sql_result.sql_query
        connection_name = sql_result.connection_name
        connection_id = sql_result.connection_id
        execution_time_ms = sql_result.execution_time_ms
        formatted_results_str = sql_result.formatted_results

        system_prompt = (
            "You are a helpful data analyst assistant. Your job is to analyze the executed SQL query and its returned results, "
            "and provide a clear, concise, and professional natural language answer to the user's original question. "
            "Make sure to format the output nicely (e.g. use markdown tables or bullet points where appropriate). "
            "Always cite values directly from the query results. If the results are empty, explain that no matching records were found.\n\n"
            "CHART OUTPUT RULE:\n"
            "If and only if your answer contains numerical data that can be meaningfully visualised (comparisons, trends, distributions, rankings, time series), "
            "append a chart specification at the very end of your response using this exact format:\n\n"
            'CHART_SPEC:{"chart_type":"bar","title":"<descriptive title>","x_key":"<field name>","y_keys":["<field name>"],"data":[{...},{...}]}\n\n'
            "Rules for the chart spec:\n"
            "- chart_type must be one of: bar, line, area, pie\n"
            "- Choose the most appropriate chart_type for the data\n"
            "- data must be a JSON array of flat objects, all objects must have the same keys\n"
            "- x_key is the categorical or time-based field\n"
            "- y_keys is an array of one or more numeric fields\n"
            "- For pie charts, y_keys must contain exactly one field\n"
            "- All values in y_keys fields must be numbers, not strings\n"
            "- The CHART_SPEC line must be on its own line at the very end of your response, after all text\n"
            "- Do not emit CHART_SPEC if the answer is narrative, qualitative, or contains no numerical comparisons\n"
            "- Do not wrap CHART_SPEC in markdown code fences"
        )

        prompt = f"""User Question: {fusion_input.query}
Generated SQL Query: {sql_query}
Query Results:
{formatted_results_str}

Please summarize and answer the user's question based on the query results. Do not make up any facts."""

        (
            selected_model_string,
            selected_provider_id,
            model_config,
            db_model,
        ) = await _resolve_model_config(
            model_id=fusion_input.model_id,
            db=db,
            user=user,
            query=fusion_input.query,
            context_chunks=[],
            has_attachments=False,
        )

        usage_done_event = None
        async for event in _stream_llm_response(
            model_config=model_config,
            default_model=default_model,
            system_prompt=system_prompt,
            prompt=prompt,
            max_tokens=4096,
            db=db,
            user=user,
        ):
            if event["type"] == "token":
                yield event
            elif event["type"] == "usage_done":
                usage_done_event = event

        full_answer = usage_done_event["full_answer"]
        was_fallback = usage_done_event["was_fallback"]
        fallback_model_name = usage_done_event["fallback_model_name"]
        db_model = usage_done_event["db_model"]
        selected_model_string = usage_done_event["model_string"]
        selected_provider_id = usage_done_event["provider_id"]

        print(
            f"[Fusion Agent] Building citations. DB citation: {bool(fusion_input.sql_result)}, Doc citations: 0, Excel citations: 0"
        )
        citations = [
            {
                "document_id": str(connection_id),
                "filename": f"Database: {connection_name}",
                "chunk_text": f"SQL: {sql_query}\nResults: {formatted_results_str[:1000]}...",
                "page_number": None,
                "slide_number": None,
                "chunk_index": 0,
            }
        ]

        serializable_results = None
        if query_results is not None:
            serializable_results = json.loads(json.dumps(query_results, default=str))

        print("[Fusion Agent] Done. Yielding done event.")
        yield {
            "type": "done",
            "answer": full_answer,
            "citations": citations,
            "model_string": selected_model_string,
            "follow_up_questions": [],
            "generated_sql": sql_query,
            "query_results": serializable_results,
            "db_connection_id": connection_id,
            "execution_time_ms": execution_time_ms,
            "status": "success",
            "error_message": None,
            "error_type": None,
            "resolved_model": db_model.display_name
            if db_model
            else selected_model_string,
            "resolved_model_id": db_model.id if db_model else None,
            "was_fallback": was_fallback,
            "fallback_model_name": fallback_model_name,
        }

    elif fusion_input.mode == "cross_source":
        print(f"[Fusion Agent] Building prompt for mode: {fusion_input.mode}")
        db_sql_query = fusion_input.sql_result.sql_query
        db_query_results = fusion_input.sql_result.query_results
        db_formatted_results = fusion_input.sql_result.formatted_results
        db_connection_name = fusion_input.sql_result.connection_name
        execution_time_ms = fusion_input.sql_result.execution_time_ms

        context_block = fusion_input.rag_result.context_block
        qdrant_results = fusion_input.rag_result.qdrant_results
        excel_results = fusion_input.rag_result.excel_results
        doc_id_to_filename = fusion_input.rag_result.doc_id_to_filename

        fusion_system_prompt = (
            "You are a helpful data analyst assistant. You have been given results from two sources: "
            "an external database (via SQL) and one or more documents or files. "
            "Your job is to answer the user's question using both sources. "
            "Decide the best format for your answer based on the question: "
            "if the question asks for a direct comparison, present both results clearly and then give a conclusion. "
            "If the question can be answered as a unified narrative using both sources, do that instead. "
            "Always cite which source each piece of information comes from. "
            "Do not make up any facts. Only use information present in the provided results."
        )

        fusion_prompt = f"""User Question: {fusion_input.query}

--- Database Source: {db_connection_name} ---
SQL Query: {db_sql_query}
Results:
{db_formatted_results}

--- Document/File Source ---
{context_block}

Answer the user's question using both sources above."""

        context_chunks = []
        for hit in qdrant_results:
            context_chunks.append(hit.get("payload", {}).get("chunk_text", ""))
        for er in excel_results:
            context_chunks.append(str(er.get("result", "")))

        (
            selected_model_string,
            selected_provider_id,
            model_config,
            db_model,
        ) = await _resolve_model_config(
            model_id=fusion_input.model_id,
            db=db,
            user=user,
            query=fusion_input.query,
            context_chunks=context_chunks,
            has_attachments=bool(fusion_input.document_id),
        )

        usage_done_event = None
        try:
            async for event in _stream_llm_response(
                model_config=model_config,
                default_model=default_model,
                system_prompt=fusion_system_prompt,
                prompt=fusion_prompt,
                max_tokens=8192,
                db=db,
                user=user,
            ):
                if event["type"] == "token":
                    yield event
                elif event["type"] == "usage_done":
                    usage_done_event = event
        except Exception as exc:
            logger.error(
                "%s streaming answer generation failed: %s", selected_provider_id, exc
            )
            error_msg = (
                "I encountered an error while generating an answer. Please try again."
            )
            usage_done_event = {
                "full_answer": error_msg,
                "was_fallback": False,
                "fallback_model_name": None,
                "db_model": db_model,
                "model_string": selected_model_string,
                "provider_id": selected_provider_id,
            }
            yield {"type": "token", "content": error_msg}

        full_answer = usage_done_event["full_answer"]
        was_fallback = usage_done_event["was_fallback"]
        fallback_model_name = usage_done_event["fallback_model_name"]
        db_model = usage_done_event["db_model"]
        selected_model_string = usage_done_event["model_string"]
        selected_provider_id = usage_done_event["provider_id"]

        if not full_answer:
            full_answer = (
                "I could not generate an answer. Please try rephrasing your question."
            )
            yield {"type": "token", "content": full_answer}

        answer_parts = re.split(r"(?i)\[follow[-_]up\]", full_answer)
        clean_answer = answer_parts[0].strip()
        follow_up_questions: list[str] = []
        if len(answer_parts) > 1:
            raw_questions = answer_parts[1].strip().split("\n")
            for q in raw_questions:
                q = q.strip().lstrip("-").lstrip("*").lstrip("123456789.").strip()
                if q:
                    follow_up_questions.append(q)

        print(
            f"[Fusion Agent] Building citations. DB citation: {bool(fusion_input.sql_result)}, Doc citations: {len(qdrant_results)}, Excel citations: {len(excel_results)}"
        )
        citations = []
        citations.append(
            {
                "document_id": str(fusion_input.database_id),
                "filename": f"Database: {db_connection_name}",
                "chunk_text": f"SQL: {db_sql_query}\nResults: {db_formatted_results[:1000]}...",
                "page_number": None,
                "slide_number": None,
                "chunk_index": 0,
            }
        )
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
        for er in excel_results:
            citations.append(
                {
                    "document_id": str(er.get("document_id", "")),
                    "filename": er.get("filename", "Unknown"),
                    "chunk_text": f"Query: {fusion_input.query}\nResult: {str(er.get('result', ''))[:1000]}",
                    "page_number": None,
                    "slide_number": None,
                    "chunk_index": 0,
                }
            )

        serializable_results = None
        if db_query_results is not None:
            serializable_results = json.loads(json.dumps(db_query_results, default=str))

        print("[Fusion Agent] Done. Yielding done event.")
        yield {
            "type": "done",
            "answer": clean_answer,
            "citations": citations,
            "model_string": selected_model_string,
            "follow_up_questions": follow_up_questions,
            "generated_sql": db_sql_query,
            "query_results": serializable_results,
            "db_connection_id": fusion_input.database_id,
            "execution_time_ms": execution_time_ms,
            "status": "success",
            "error_message": None,
            "error_type": None,
            "resolved_model": db_model.display_name
            if db_model
            else selected_model_string,
            "resolved_model_id": db_model.id if db_model else None,
            "was_fallback": was_fallback,
            "fallback_model_name": fallback_model_name,
        }

    elif fusion_input.mode == "doc_only":
        print(f"[Fusion Agent] Building prompt for mode: {fusion_input.mode}")
        context_block = fusion_input.rag_result.context_block
        qdrant_results = fusion_input.rag_result.qdrant_results
        excel_results = fusion_input.rag_result.excel_results
        doc_id_to_filename = fusion_input.rag_result.doc_id_to_filename

        final_prompt = f"""Context:
    {context_block}

    Conversation History (recent messages):
    {fusion_input.conversation_history if fusion_input.conversation_history else "No previous messages."}

    User Question: {fusion_input.query}

    Answer:"""

        system_prompt = rag_service._SYSTEM_PROMPT
        if fusion_input.command_instruction:
            system_prompt += f"\n\n[Instructions]\n{fusion_input.command_instruction}"

        context_chunks = []
        for hit in qdrant_results:
            context_chunks.append(hit.get("payload", {}).get("chunk_text", ""))
        for er in excel_results:
            context_chunks.append(str(er.get("result", "")))

        (
            selected_model_string,
            selected_provider_id,
            model_config,
            db_model,
        ) = await _resolve_model_config(
            model_id=fusion_input.model_id,
            db=db,
            user=user,
            query=fusion_input.query,
            context_chunks=context_chunks,
            has_attachments=bool(fusion_input.document_id),
        )

        was_fallback = False
        fallback_model_name = None

        usage_done_event = None
        try:
            async for event in _stream_llm_response(
                model_config=model_config,
                default_model=default_model,
                system_prompt=system_prompt,
                prompt=final_prompt,
                max_tokens=8192,
                db=db,
                user=user,
            ):
                if event["type"] == "token":
                    yield event
                elif event["type"] == "usage_done":
                    usage_done_event = event
        except Exception as exc:
            logger.error(
                "%s streaming answer generation failed: %s", selected_provider_id, exc
            )
            error_msg = (
                "I encountered an error while generating an answer. Please try again."
            )
            usage_done_event = {
                "full_answer": error_msg,
                "was_fallback": was_fallback,
                "fallback_model_name": fallback_model_name,
                "db_model": db_model,
                "model_string": selected_model_string,
                "provider_id": selected_provider_id,
            }
            yield {"type": "token", "content": error_msg}

        full_answer = usage_done_event["full_answer"]
        was_fallback = usage_done_event["was_fallback"]
        fallback_model_name = usage_done_event["fallback_model_name"]
        db_model = usage_done_event["db_model"]
        selected_model_string = usage_done_event["model_string"]
        selected_provider_id = usage_done_event["provider_id"]

        if not full_answer:
            full_answer = (
                "I could not generate an answer. Please try rephrasing your question."
            )
            yield {"type": "token", "content": full_answer}

        answer_parts = re.split(r"(?i)\[follow[-_]up\]", full_answer)
        clean_answer = answer_parts[0].strip()
        follow_up_questions: list[str] = []
        if len(answer_parts) > 1:
            raw_questions = answer_parts[1].strip().split("\n")
            for q in raw_questions:
                q = q.strip().lstrip("-").lstrip("*").lstrip("123456789.").strip()
                if q:
                    follow_up_questions.append(q)

        print(
            f"[Fusion Agent] Building citations. DB citation: {bool(fusion_input.sql_result)}, Doc citations: {len(qdrant_results)}, Excel citations: {len(excel_results)}"
        )
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

        print("[Fusion Agent] Done. Yielding done event.")
        yield {
            "type": "done",
            "answer": clean_answer,
            "citations": citations,
            "model_string": selected_model_string,
            "follow_up_questions": follow_up_questions,
            "resolved_model": db_model.display_name
            if db_model
            else selected_model_string,
            "resolved_model_id": db_model.id if db_model else None,
            "was_fallback": was_fallback,
            "fallback_model_name": fallback_model_name,
        }
