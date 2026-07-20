import uuid
import asyncio
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.enums import DocumentStatus
import app.services.rag_service as rag_service
from app.services.agents.types import RAGAgentResult

logger = rag_service.logger


async def run_rag_agent(
    query: str,
    query_vector: list[float],
    user: User,
    db: Session,
    document_id: Optional[uuid.UUID],
    compare_document_ids: Optional[list[uuid.UUID]],
    is_compare_mode: bool,
    is_summarize_mode: bool,
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

    if is_compare_mode and compare_document_ids:
        print(
            f"[RAG Agent] Running compare mode resolution for {len(compare_document_ids)} documents..."
        )
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
        print(f"[RAG Agent] Context block built. Length: {len(context_block)} chars")

    else:
        # Standard search/retrieval path: run Qdrant search and Excel pipeline concurrently.
        excel_docs_to_run = [doc for doc in excel_docs if doc.excel_schema]
        print(
            f"[RAG Agent] Running standard retrieval. Non-excel docs exist: {non_excel_exist}, Excel docs: {len(excel_docs_to_run)}"
        )

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
                    query=query,
                    query_vector=query_vector,
                    collection_name=collection_name,
                    role_ids=search_role_ids,
                    document_id=str(document_id) if document_id else None,
                    limit=15,
                )
            )
            branches.append("qdrant")

        if excel_docs_to_run:

            async def run_excel():
                sub_results = await asyncio.gather(
                    *[
                        rag_service._run_excel_query(doc, query)
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
            f"[RAG Agent] Qdrant search complete. Hits before rerank: {len(qdrant_results)}"
        )
        print(f"[RAG Agent] Excel query complete. Results: {len(excel_results)}")

        # Filter out any orphaned Qdrant vectors (e.g. from deleted documents)
        qdrant_results = [
            hit
            for hit in qdrant_results
            if hit.get("payload", {}).get("document_id") in doc_id_to_filename
        ]

        qdrant_results = await rag_service._rerank_chunks(query, qdrant_results)

        # Truncate candidates: allow more chunks (8) for summarize mode
        final_limit = 8 if (is_summarize_mode and document_id) else 5
        qdrant_results = qdrant_results[:final_limit]
        print(
            f"[RAG Agent] Reranking complete. Chunks after truncation: {len(qdrant_results)}"
        )

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
                    f"Source: {er['filename']}\nQuery: {query}\nResult: {er['result']}"
                )
                context_parts.append("---")

        context_block = (
            "\n".join(context_parts) if context_parts else "No relevant context found."
        )
        print(f"[RAG Agent] Context block built. Length: {len(context_block)} chars")

    print("[RAG Agent] Done. Returning result.")
    return RAGAgentResult(
        success=True,
        qdrant_results=qdrant_results,
        excel_results=excel_results,
        context_block=context_block,
        doc_id_to_filename=doc_id_to_filename,
    )
