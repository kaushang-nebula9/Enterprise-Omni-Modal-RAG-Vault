import uuid
import asyncio
from typing import Optional, AsyncGenerator
from sqlalchemy.orm import Session

from app.models.user import User
from app.services import embedding_service
import app.services.rag_service as rag_service
from app.services.agents.types import RAGAgentResult, FusionInput
from app.services.agents.sql_agent import run_sql_agent
from app.services.agents.rag_agent import run_rag_agent
from app.services.agents.fusion_agent import run_fusion_agent

logger = rag_service.logger


async def run_orchestrator(
    query: str,
    user: User,
    db: Session,
    conversation_history: str,
    document_id: Optional[uuid.UUID],
    database_id: Optional[uuid.UUID],
    command_instruction: Optional[str],
    compare_document_ids: Optional[list[uuid.UUID]],
    is_compare_mode: bool,
    is_summarize_mode: bool,
    model_id: Optional[uuid.UUID],
    session_id: Optional[uuid.UUID],
) -> AsyncGenerator[dict, None]:
    print(f"[Orchestrator] Query received: {query[:100]}")
    print("[Orchestrator] Embedding query vector...")
    # Embed the query vector once
    query_vector = embedding_service.embed_text(query)

    # Determine initial mode
    if database_id and document_id and rag_service.is_cross_source_query(query):
        mode = "cross_source"
    elif database_id:
        mode = "db_only"
    else:
        mode = "doc_only"

    print(f"[Orchestrator] Mode determined: {mode}")
    print(f"[Orchestrator] Launching agents for mode: {mode}")

    if mode == "cross_source":
        # Run SQL Agent and RAG Agent in parallel
        # We start RAG Agent as an asyncio Task since it is a coroutine
        rag_task = asyncio.create_task(
            run_rag_agent(
                query=query,
                query_vector=query_vector,
                user=user,
                db=db,
                document_id=document_id,
                compare_document_ids=compare_document_ids,
                is_compare_mode=is_compare_mode,
                is_summarize_mode=is_summarize_mode,
            )
        )

        sql_result = None
        # Consume SQL Agent generator and forward its progress tokens immediately
        async for event in run_sql_agent(
            query=query,
            user=user,
            db=db,
            database_id=database_id,
            model_id=model_id,
            session_id=session_id,
        ):
            if event.get("type") == "agent_result":
                sql_result = event["result"]
            else:
                yield event

        try:
            rag_result = await rag_task
        except Exception as e:
            logger.error("RAG Agent failed in cross_source mode: %s", e)
            rag_result = RAGAgentResult(success=False)

        # Degradation logic
        if not sql_result or not sql_result.success:
            degraded_mode = "doc_only"
            print(f"[Orchestrator] SQL Agent failed - degrading to: {degraded_mode}")
            mode = degraded_mode
        elif not rag_result or not rag_result.success:
            mode = "db_only"

    elif mode == "db_only":
        sql_result = None
        async for event in run_sql_agent(
            query=query,
            user=user,
            db=db,
            database_id=database_id,
            model_id=model_id,
            session_id=session_id,
        ):
            if event.get("type") == "agent_result":
                sql_result = event["result"]
            else:
                yield event

        # Degradation: if SQL Agent failed -> degrade to "doc_only", run RAG Agent
        if not sql_result or not sql_result.success:
            degraded_mode = "doc_only"
            print(f"[Orchestrator] SQL Agent failed - degrading to: {degraded_mode}")
            mode = degraded_mode
            rag_result = await run_rag_agent(
                query=query,
                query_vector=query_vector,
                user=user,
                db=db,
                document_id=document_id,
                compare_document_ids=compare_document_ids,
                is_compare_mode=is_compare_mode,
                is_summarize_mode=is_summarize_mode,
            )
        else:
            rag_result = None

    else:  # doc_only
        sql_result = None
        rag_result = await run_rag_agent(
            query=query,
            query_vector=query_vector,
            user=user,
            db=db,
            document_id=document_id,
            compare_document_ids=compare_document_ids,
            is_compare_mode=is_compare_mode,
            is_summarize_mode=is_summarize_mode,
        )

    print("[Orchestrator] All agents completed. Handing off to Fusion Agent.")

    # Construct FusionInput and run Fusion Agent
    fusion_input = FusionInput(
        query=query,
        conversation_history=conversation_history,
        command_instruction=command_instruction,
        model_id=model_id,
        sql_result=sql_result,
        rag_result=rag_result,
        mode=mode,
        database_id=database_id,
        document_id=document_id,
    )

    async for event in run_fusion_agent(
        fusion_input=fusion_input,
        user=user,
        db=db,
    ):
        yield event
