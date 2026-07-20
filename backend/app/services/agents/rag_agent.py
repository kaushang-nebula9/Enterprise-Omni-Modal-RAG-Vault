import uuid
import asyncio
import json
import re
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.enums import DocumentStatus
from app.services import embedding_service
import app.services.rag_service as rag_service
from app.services.agents.types import RAGAgentResult

logger = rag_service.logger


async def _call_reformulate_llm(
    query: str,
    current_query: str,
    previous_context_block: Optional[str],
    previous_judgment: Optional[dict],
    instruction: Optional[str],
) -> str:
    """Calls Anthropic Claude Haiku to reformulate a query based on prior feedback."""
    try:
        client = rag_service._get_async_anthropic_client()
        reformulate_system = (
            "You are a query reformulation specialist. A RAG retrieval attempt returned context "
            "that was not sufficiently relevant to the user's question. "
            "Your job is to reformulate the query to improve retrieval quality. "
            "Respond ONLY with a JSON object in this exact format with no other text:\n"
            '{"reformulated_query": "the improved query string", "reasoning": "one sentence on what you changed and why"}'
        )

        reformulate_prompt = f"""Original Query: {query}
Previous Retrieval Query Used: {current_query}
Retrieved Context (that was insufficient):
{previous_context_block[:500] if previous_context_block else "None"}
Judge Feedback: {previous_judgment.get("reasoning", "") if previous_judgment else ""}
Instruction from Orchestrator: {instruction or "None"}

Reformulate the query to retrieve more relevant context."""

        response = await client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=256,
            system=reformulate_system,
            messages=[{"role": "user", "content": reformulate_prompt}],
        )

        text = response.content[0].text.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
        res = json.loads(text)
        if "reformulated_query" in res:
            return res["reformulated_query"]
    except Exception as exc:
        logger.warning("Reformulation LLM call failed: %s", exc)
    return query


async def _call_rag_judge(
    query: str,
    context_block: str,
    qdrant_results: list[dict],
    excel_results: list[dict],
) -> dict:
    """Calls Anthropic Claude Haiku to evaluate retrieval quality/relevance."""
    if context_block == "No relevant context found." or not context_block.strip():
        return {
            "sufficient": False,
            "confidence": 0.0,
            "reasoning": "No context retrieved",
            "fix_instruction": "Try broader search terms",
        }
    try:
        client = rag_service._get_async_anthropic_client()
        judge_system = (
            "You are a retrieval quality evaluator. Given a user query and the retrieved context chunks, "
            "evaluate whether the context is sufficiently relevant to answer the query. "
            "Respond ONLY with a JSON object in this exact format with no other text:\n"
            '{"sufficient": true/false, "confidence": 0.0-1.0, "reasoning": "one sentence explanation", '
            '"fix_instruction": "if not sufficient, one sentence on how to reformulate the query to get better results, else empty string"}'
        )

        judge_prompt = f"""User Query: {query}
Retrieved Context:
{context_block[:1500]}
Number of chunks retrieved: {len(qdrant_results)}
Number of Excel results: {len(excel_results)}"""

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
        logger.warning("RAG Judge LLM call failed or parsed incorrectly: %s", exc)
        return {
            "sufficient": True,
            "confidence": 0.7,
            "reasoning": "Judge unavailable",
            "fix_instruction": "",
        }


async def run_rag_agent(
    query: str,
    user: User,
    db: Session,
    document_id: Optional[uuid.UUID],
    compare_document_ids: Optional[list[uuid.UUID]],
    is_compare_mode: bool,
    is_summarize_mode: bool,
    instruction: Optional[str] = None,
    max_attempts: int = 3,
) -> RAGAgentResult:
    print(
        f"[RAG Agent] Starting. document_id={document_id}, is_compare_mode={is_compare_mode}"
    )

    tenant_id = str(user.tenant_id)
    role_id = str(user.role_id)
    search_role_ids = [role_id, str(user.id)]

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
    print(f"[RAG Agent] Authorized docs found: {len(all_authorized_docs)}")

    if not all_authorized_docs:
        print("[RAG Agent] No authorized documents found. Returning empty result.")
        return RAGAgentResult(
            success=False,
            reasoning="No authorized documents found for this user.",
            confidence=0.0,
        )

    excel_docs = [
        d for d in all_authorized_docs if d.file_type in rag_service.TABULAR_FILE_TYPES
    ]
    non_excel_exist = any(
        d.file_type not in rag_service.TABULAR_FILE_TYPES for d in all_authorized_docs
    )

    # Build a lookup of document_id -> filename
    doc_id_to_filename: dict[str, str] = {
        str(doc.id): doc.filename for doc in all_authorized_docs
    }

    context_parts: list[str] = []
    qdrant_results: list[dict] = []
    excel_results: list[dict] = []

    # Compare Mode Path
    if is_compare_mode and compare_document_ids:
        print(
            f"[RAG Agent] Compare mode. Resolving {len(compare_document_ids)} documents..."
        )
        query_vector = embedding_service.embed_text(query)

        compare_docs_db = (
            db.query(Document).filter(Document.id.in_(compare_document_ids)).all()
        )
        compare_id_to_doc = {str(d.id): d for d in compare_docs_db}

        # Make sure compare docs are in doc_id_to_filename so citation lookups work
        for did_str, doc in compare_id_to_doc.items():
            doc_id_to_filename.setdefault(did_str, doc.filename)

        resolutions = await asyncio.gather(
            *[
                rag_service._resolve_compare_document(
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
        print(
            f"[RAG Agent] Compare mode complete. Context length: {len(context_block)} chars"
        )
        return RAGAgentResult(
            success=True,
            qdrant_results=qdrant_results,
            excel_results=[],
            context_block=context_block,
            doc_id_to_filename=doc_id_to_filename,
            confidence=1.0,
            reasoning="Compare mode - no evaluation needed.",
            attempts=1,
        )

    # Standard Retrieval Path (ReAct Loop)
    attempt = 1
    current_query = query
    previous_context_block = None
    previous_judgment = None
    context_block = "No relevant context found."
    judgment = {
        "sufficient": False,
        "confidence": 0.0,
        "reasoning": "No attempts completed",
        "fix_instruction": "",
    }

    while attempt <= max_attempts:
        # REASON
        if attempt >= 2:
            current_query = await _call_reformulate_llm(
                query,
                current_query,
                previous_context_block,
                previous_judgment,
                instruction,
            )
            print(
                f"[RAG Agent] Attempt {attempt}/{max_attempts}. Reformulated query: {current_query}"
            )

        # ACT
        print(f"[RAG Agent] Attempt {attempt} - Embedding and retrieving...")
        query_vector = embedding_service.embed_text(current_query)

        coroutines = []
        branches = []

        if non_excel_exist:
            collection_name = (
                all_authorized_docs[0].qdrant_collection
                if document_id and all_authorized_docs
                else f"tenant_{tenant_id}"
            )
            coroutines.append(
                rag_service._run_qdrant_search(
                    query=current_query,
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
                    *[
                        rag_service._run_excel_query(doc, current_query)
                        for doc in excel_docs_to_run
                    ]
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

        print(
            f"[RAG Agent] Attempt {attempt} - Qdrant hits: {len(qdrant_results)}, Excel results: {len(excel_results)}"
        )

        # Filter out any orphaned Qdrant vectors (e.g. from deleted documents)
        qdrant_results = [
            hit
            for hit in qdrant_results
            if hit.get("payload", {}).get("document_id") in doc_id_to_filename
        ]

        qdrant_results = await rag_service._rerank_chunks(current_query, qdrant_results)

        # Truncate candidates: allow more chunks (8) for summarize mode
        final_limit = 8 if (is_summarize_mode and document_id) else 5
        qdrant_results = qdrant_results[:final_limit]
        print(
            f"[RAG Agent] Attempt {attempt} - Reranking complete. Chunks after truncation: {len(qdrant_results)}"
        )

        context_parts = []
        if qdrant_results:
            context_parts.append("[Document Chunks]")
            for hit in qdrant_results:
                filename = doc_id_to_filename.get(
                    hit.get("payload", {}).get("document_id", ""), "Unknown"
                )
                context_parts.append(rag_service._format_chunk_context(filename, hit))
                context_parts.append("---")

        if excel_results:
            context_parts.append("[Excel Data Results]")
            for er in excel_results:
                context_parts.append(
                    f"Source: {er['filename']}\nQuery: {current_query}\nResult: {er['result']}"
                )
                context_parts.append("---")

        context_block = (
            "\n".join(context_parts) if context_parts else "No relevant context found."
        )
        print(
            f"[RAG Agent] Attempt {attempt} - Context block length: {len(context_block)} chars"
        )

        # OBSERVE
        judgment = await _call_rag_judge(
            query, context_block, qdrant_results, excel_results
        )
        print(
            f"[RAG Agent] Judge evaluation - sufficient: {judgment['sufficient']}, confidence: {judgment['confidence']}"
        )
        print(f"[RAG Agent] Judge reasoning: {judgment['reasoning']}")

        # DECIDE
        if judgment["sufficient"] or attempt == max_attempts:
            if judgment["sufficient"]:
                print(
                    f"[RAG Agent] Context sufficient. Returning after {attempt} attempt(s)."
                )
            else:
                print(
                    f"[RAG Agent] All {max_attempts} attempts exhausted. Returning best available result."
                )
            break
        else:
            print("[RAG Agent] Context insufficient. Reformulating and retrying...")
            previous_context_block = context_block
            previous_judgment = judgment
            attempt += 1

    success_val = True
    if context_block == "No relevant context found." or not (
        qdrant_results or excel_results
    ):
        success_val = False

    print(
        f"[RAG Agent] Done. Returning result. Confidence: {judgment.get('confidence', 1.0)}"
    )
    return RAGAgentResult(
        success=success_val,
        qdrant_results=qdrant_results,
        excel_results=excel_results,
        context_block=context_block,
        doc_id_to_filename=doc_id_to_filename,
        confidence=judgment.get("confidence", 1.0),
        reasoning=judgment.get("reasoning", ""),
        attempts=attempt,
        reformulated_query=current_query if current_query != query else None,
    )
