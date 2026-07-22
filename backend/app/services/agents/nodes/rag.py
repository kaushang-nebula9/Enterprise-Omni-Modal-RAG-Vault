# RAG agent node and RAG judge node

import uuid
import asyncio
from sqlalchemy import or_
from app.db.session import SessionLocal
from app.services.agents.types import AgentState, RAGAgentResult
from app.models.user import User
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.enums import DocumentStatus
from app.services import embedding_service
import app.services.rag_service as rag_service
import re
import json
from typing import Optional

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
            model="claude-haiku-4-5-20251001",
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
        logger.warning("RAG Judge LLM call failed or parsed incorrectly: %s", exc)
        return {
            "sufficient": True,
            "confidence": 0.7,
            "reasoning": "Judge unavailable",
            "fix_instruction": "",
        }


async def excel_agent(doc, query: str) -> Optional[dict]:
    print(f"[Excel Agent] Attempt 1 for {doc.filename}")
    result, error = await rag_service._run_excel_query(doc, query)
    if result is not None:
        return result

    print(
        f"[Excel Agent] Attempt 1 failed for {doc.filename}. Retrying with error feedback."
    )

    judgment = {"pandas_code": "", "reasoning": ""}
    try:
        client = rag_service._get_async_anthropic_client()
        system_prompt = (
            "You are a pandas code generation specialist. A previous attempt to generate pandas code to answer a user query against an Excel file failed during execution. \n"
            "Your job is to generate corrected pandas code.\n"
            "The dataframe is already loaded as the variable `df`.\n"
            "Respond ONLY with a JSON object in this exact format with no other text:\n"
            '{"pandas_code": "the corrected pandas code as a single string", "reasoning": "one sentence on what you changed"}'
        )

        user_prompt = f"""Excel File: {doc.filename}
        Schema: {json.dumps(doc.excel_schema)}
        User Query: {query}
        Previous attempt failed during execution.
        Execution Error: {error}
        Generate corrected pandas code to answer the query.
        The dataframe is loaded as `df`. Return only the final result as a variable named `result`."""

        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
        parsed = json.loads(text)
        if "pandas_code" in parsed:
            judgment = parsed
    except Exception as exc:
        logger.warning("Excel Agent LLM call failed or parsed incorrectly: %s", exc)
        print(
            f"[Excel Agent] Attempt 2 also failed for {doc.filename}. Returning None."
        )
        return None

    code = judgment.get("pandas_code", "").strip()
    if not code:
        print(
            f"[Excel Agent] Attempt 2 also failed for {doc.filename}. Returning None."
        )
        return None

    # Strip markdown fences if present
    if code.startswith("```"):
        code = code.split("\n", 1)[-1]
        if code.endswith("```"):
            code = code[: -len("```")].strip()

    if not code:
        print(
            f"[Excel Agent] Attempt 2 also failed for {doc.filename}. Returning None."
        )
        return None

    # Replicate execution mechanism of execute_excel_query
    try:
        import pandas as pd
        import threading
        from RestrictedPython import compile_restricted, safe_globals
        from RestrictedPython.Guards import guarded_iter_unpack_sequence
        from RestrictedPython.Eval import (
            default_guarded_getitem,
            default_guarded_getiter,
        )

        # Load dataframe
        abs_path = rag_service.get_absolute_path(doc.file_path)
        df = rag_service.load_dataframe(abs_path, doc.file_type)

        compiled = compile_restricted(code, filename="<excel_query>", mode="exec")

        restricted_globals = dict(safe_globals)
        restricted_globals["_getattr_"] = getattr
        restricted_globals["_getitem_"] = default_guarded_getitem
        restricted_globals["_getiter_"] = default_guarded_getiter
        restricted_globals["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
        restricted_globals["_write_"] = lambda x: x
        restricted_globals["pd"] = pd

        restricted_locals = {"df": df}

        result_container = {"result": None, "error": None}

        def _execute():
            try:
                exec(compiled, restricted_globals, restricted_locals)
                result_container["result"] = restricted_locals.get("result")
            except Exception as exc:
                result_container["error"] = str(exc)

        thread = threading.Thread(target=_execute, daemon=True)
        thread.start()
        thread.join(timeout=10)

        if thread.is_alive():
            logger.warning("Excel query execution timed out (10s) on attempt 2")
            print(
                f"[Excel Agent] Attempt 2 also failed for {doc.filename}. Returning None."
            )
            return None

        if result_container["error"]:
            logger.debug(
                "Excel query execution error on attempt 2: %s",
                result_container["error"],
            )
            print(
                f"[Excel Agent] Attempt 2 also failed for {doc.filename}. Returning None."
            )
            return None

        result = result_container["result"]
        if result is None:
            print(
                f"[Excel Agent] Attempt 2 also failed for {doc.filename}. Returning None."
            )
            return None

        print(f"[Excel Agent] Attempt 2 succeeded for {doc.filename}")
        return {
            "filename": doc.filename,
            "document_id": str(doc.id),
            "result": str(result),
        }

    except Exception as exc:
        logger.error("excel_agent attempt 2 execution failed: %s", exc)
        print(
            f"[Excel Agent] Attempt 2 also failed for {doc.filename}. Returning None."
        )
        return None


def get_db_session():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


async def rag_node(state: AgentState) -> dict:

    print(f"[RAG Node] Attempt {state['rag_attempts'] + 1}/{state['rag_max_attempts']}")
    db = get_db_session()
    try:
        query = state["query"]
        document_id = state["document_id"]
        compare_document_ids = state["compare_document_ids"]
        is_compare_mode = state["is_compare_mode"]
        is_summarize_mode = state["is_summarize_mode"]
        rag_attempts = state["rag_attempts"]
        rag_fix_instruction = state["rag_fix_instruction"]

        # Fetch user
        user = db.query(User).filter(User.id == uuid.UUID(state["user_id"])).first()
        if not user:
            return {
                "rag_result": RAGAgentResult(
                    success=False,
                    reasoning="User not found.",
                    confidence=0.0,
                ),
                "rag_attempts": rag_attempts + 1,
            }

        # Determine current query
        current_query = query
        if rag_attempts > 0 and rag_fix_instruction:
            previous_context_block = (
                state["rag_result"].context_block if state.get("rag_result") else None
            )
            previous_judgment = {
                "sufficient": state.get("rag_sufficient", False),
                "reasoning": state.get("rag_judge_reasoning", ""),
                "fix_instruction": rag_fix_instruction,
            }
            current_query = await _call_reformulate_llm(
                query=query,
                current_query=state["rag_result"].reformulated_query
                if (state.get("rag_result") and state["rag_result"].reformulated_query)
                else query,
                previous_context_block=previous_context_block,
                previous_judgment=previous_judgment,
                instruction=state.get("command_instruction"),
            )

        print(f"[RAG Node] current_query: {current_query}")

        # Fetch authorized docs
        tenant_id = str(user.tenant_id)
        role_id = str(user.role_id)
        search_role_ids = [role_id, str(user.id)]

        doc_id_uuid = (
            uuid.UUID(document_id) if isinstance(document_id, str) else document_id
        )
        compare_doc_ids_uuids = None
        if compare_document_ids:
            compare_doc_ids_uuids = [
                uuid.UUID(did) if isinstance(did, str) else did
                for did in compare_document_ids
            ]

        docs_query = (
            db.query(Document)
            .outerjoin(
                DocumentAccessPolicy, Document.id == DocumentAccessPolicy.document_id
            )
            .filter(
                Document.tenant_id == user.tenant_id,
                Document.status == DocumentStatus.ready,
                Document.is_archived.is_(False),
                or_(
                    DocumentAccessPolicy.role_id == user.role_id,
                    Document.uploaded_by == user.id,
                ),
            )
        )

        if compare_doc_ids_uuids:
            docs_query = docs_query.filter(Document.id.in_(compare_doc_ids_uuids))
        elif doc_id_uuid:
            docs_query = docs_query.filter(Document.id == doc_id_uuid)

        all_authorized_docs = docs_query.distinct().all()

        if not all_authorized_docs:
            print("[RAG Node] No authorized documents found. Returning empty result.")
            return {
                "rag_result": RAGAgentResult(
                    success=False,
                    reasoning="No authorized documents found for this user.",
                    confidence=0.0,
                ),
                "rag_attempts": rag_attempts + 1,
            }

        excel_docs = [
            d
            for d in all_authorized_docs
            if d.file_type in rag_service.TABULAR_FILE_TYPES
        ]
        non_excel_exist = any(
            d.file_type not in rag_service.TABULAR_FILE_TYPES
            for d in all_authorized_docs
        )

        doc_id_to_filename: dict[str, str] = {
            str(doc.id): doc.filename for doc in all_authorized_docs
        }

        # Compare Mode Path
        if is_compare_mode and compare_doc_ids_uuids:
            print(
                f"[RAG Node] Compare mode. Resolving {len(compare_doc_ids_uuids)} documents..."
            )
            query_vector = embedding_service.embed_text(query)

            compare_docs_db = (
                db.query(Document).filter(Document.id.in_(compare_doc_ids_uuids)).all()
            )
            compare_id_to_doc = {str(d.id): d for d in compare_docs_db}

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
                    for did_uuid in compare_doc_ids_uuids
                ],
                return_exceptions=True,
            )

            context_parts = []
            qdrant_results = []
            for did_uuid, resolution in zip(compare_doc_ids_uuids, resolutions):
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
                "\n".join(context_parts)
                if context_parts
                else "No relevant context found."
            )
            print(
                f"[RAG Node] Compare mode complete. Context length: {len(context_block)} chars"
            )

            excel_results = []
            print(
                f"[RAG Node] Qdrant hits: {len(qdrant_results)}, Excel results: {len(excel_results)}"
            )
            print(f"[RAG Node] Context block length: {len(context_block)} chars")

            return {
                "rag_result": RAGAgentResult(
                    success=True,
                    qdrant_results=qdrant_results,
                    excel_results=excel_results,
                    context_block=context_block,
                    doc_id_to_filename=doc_id_to_filename,
                    confidence=1.0,
                    reasoning="Compare mode - no evaluation needed.",
                    attempts=rag_attempts + 1,
                ),
                "rag_attempts": rag_attempts + 1,
                "rag_sufficient": True,
            }

        # Standard Retrieval Path
        query_vector = embedding_service.embed_text(current_query)

        coroutines = []
        branches = []
        qdrant_results = []
        excel_results = []

        if non_excel_exist:
            collection_name = (
                all_authorized_docs[0].qdrant_collection
                if doc_id_uuid and all_authorized_docs
                else f"tenant_{tenant_id}"
            )
            coroutines.append(
                rag_service._run_qdrant_search(
                    query=current_query,
                    query_vector=query_vector,
                    collection_name=collection_name,
                    role_ids=search_role_ids,
                    document_id=str(doc_id_uuid) if doc_id_uuid else None,
                    limit=15,
                )
            )
            branches.append("qdrant")

        excel_docs_to_run = [doc for doc in excel_docs if doc.excel_schema]
        if excel_docs_to_run:

            async def run_excel():
                sub_results = await asyncio.gather(
                    *[excel_agent(doc, current_query) for doc in excel_docs_to_run]
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
            f"[RAG Node] Qdrant hits: {len(qdrant_results)}, Excel results: {len(excel_results)}"
        )

        # Filter out orphaned Qdrant vectors
        qdrant_results = [
            hit
            for hit in qdrant_results
            if hit.get("payload", {}).get("document_id") in doc_id_to_filename
        ]

        qdrant_results = await rag_service._rerank_chunks(current_query, qdrant_results)

        # Truncate candidates
        final_limit = 8 if (is_summarize_mode and doc_id_uuid) else 5
        qdrant_results = qdrant_results[:final_limit]

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
        print(f"[RAG Node] Context block length: {len(context_block)} chars")

        return {
            "rag_result": RAGAgentResult(
                success=bool(qdrant_results or excel_results),
                qdrant_results=qdrant_results,
                excel_results=excel_results,
                context_block=context_block,
                doc_id_to_filename=doc_id_to_filename,
                attempts=rag_attempts + 1,
                reformulated_query=current_query if current_query != query else None,
            ),
            "rag_attempts": rag_attempts + 1,
        }
    finally:
        db.close()


async def rag_judge_node(state: AgentState) -> dict:
    rag_result = state.get("rag_result")
    if not rag_result:
        rag_result = RAGAgentResult(success=False)

    if (
        not rag_result.success
        or rag_result.context_block == "No relevant context found."
    ):
        judgment = {
            "sufficient": False,
            "confidence": 0.0,
            "reasoning": "No context retrieved",
            "fix_instruction": "Try broader search terms",
        }
    else:
        judgment = await _call_rag_judge(
            query=state["query"],
            context_block=rag_result.context_block,
            qdrant_results=rag_result.qdrant_results,
            excel_results=rag_result.excel_results,
        )

    print(
        f"[RAG Judge] sufficient={judgment['sufficient']}, confidence={judgment['confidence']}"
    )
    print(f"[RAG Judge] reasoning: {judgment['reasoning']}")

    # Merge results preserving RAGAgentResult
    updated_dict = {**rag_result.__dict__}
    updated_dict["confidence"] = judgment["confidence"]
    updated_dict["reasoning"] = judgment["reasoning"]

    return {
        "rag_sufficient": judgment["sufficient"],
        "rag_judge_reasoning": judgment["reasoning"],
        "rag_fix_instruction": judgment.get("fix_instruction", ""),
        "rag_result": RAGAgentResult(**updated_dict),
    }
