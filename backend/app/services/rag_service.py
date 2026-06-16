"""
RAG (Retrieval-Augmented Generation) service.

Handles:
  - Excel query execution in a RestrictedPython sandbox
  - Full RAG pipeline: embed query → Qdrant search → Excel pipeline → LLM answer
"""
import logging
import threading
import traceback
from typing import Optional

import pandas as pd
from RestrictedPython import compile_restricted, safe_globals
from sqlalchemy.orm import Session
from sqlalchemy import or_

from google import genai
from google.genai import types as genai_types

from app.core.config import settings
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.enums import FileType, DocumentStatus, Visibility
from app.models.user import User
from app.services import embedding_service
from app.services.qdrant_service import search_vectors
from app.services.storage_service import get_absolute_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


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
    Generate a pandas query via Gemini and execute it in a RestrictedPython
    sandbox with a 10-second timeout.

    Returns str(result) on success, None on any failure.
    """
    try:
        # Load the dataframe
        print("### 1\n")
        df = pd.read_excel(file_path, engine="openpyxl")

        print("###  2\n")
        # Ask Gemini to generate the pandas code
        prompt = _EXCEL_CODE_PROMPT.format(
            columns=schema.get("columns", []),
            dtypes=schema.get("dtypes", {}),
            rows=schema.get("shape", {}).get("rows", 0),
            cols=schema.get("shape", {}).get("columns", 0),
            sample=schema.get("sample", []),
            query=query,
        )

        print("###  3 prompt: ", prompt, "\n")
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )
        print("###  4 resonse: ", response.text, "\n")
        code = (response.text or "").strip()

        print("###  5\n")
        # Strip markdown fences if present
        if code.startswith("```"):
            code = code.split("\n", 1)[-1]
            if code.endswith("```"):
                code = code[: -len("```")].strip()

        print("###  6 code: ", code, "\n")
        if not code:
            logger.warning("Gemini returned empty code for Excel query")
            return None

        print("###  7\n")
        # Compile with RestrictedPython
        compiled = compile_restricted(code, filename="<excel_query>", mode="exec")

        print("###  8\n")
        # Build restricted globals — only allow df and safe builtins
        from RestrictedPython.Guards import guarded_iter_unpack_sequence
        from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter

        print("###  9\n")
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
        print("###  10\n")

        # Execution with a 10-second timeout (threading approach for Windows)
        result_container: dict = {"result": None, "error": None}

        print("###  11\n")
        def _execute():
            try:
                exec(compiled, restricted_globals, restricted_locals)  # noqa: S102
                result_container["result"] = restricted_locals.get("result")
            except Exception as exc:
                result_container["error"] = str(exc)

        print("###  12\n")
        thread = threading.Thread(target=_execute, daemon=True)
        thread.start()
        thread.join(timeout=10)

        print("###  13\n")
        if thread.is_alive():
            logger.warning("Excel query execution timed out (10s)")
            return None

        print("###  14\n")
        if result_container["error"]:
            print("###  15: ", result_container["error"])
            logger.debug("Excel query execution error: %s", result_container["error"])
            return None

        result = result_container["result"]
        print("###  15 result: ", result, "\n")
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
Do not make up information. Be concise and accurate."""


def run_rag_pipeline(
    query: str,
    user: User,
    db: Session,
    conversation_history: str = "",
) -> dict:
    """
    Main RAG pipeline:
      1. Embed the user query
      2. Fetch authorised documents
      3. Qdrant semantic search (non-Excel)
      4. Excel code-gen pipeline
      5. Build context → Gemini → return answer + citations
    """
    tenant_id = str(user.tenant_id)
    role_id = str(user.role_id)

    # ------------------------------------------------------------------
    # 1. Embed the query
    # ------------------------------------------------------------------
    query_vector = embedding_service.embed_text(query)

    # Fetch documents accessible via role-based access policies or uploaded by the user
    all_authorized_docs = (
        db.query(Document)
        .outerjoin(DocumentAccessPolicy, Document.id == DocumentAccessPolicy.document_id)
        .filter(
            Document.tenant_id == user.tenant_id,
            Document.status == DocumentStatus.ready,
            or_(
                DocumentAccessPolicy.role_id == user.role_id,
                Document.uploaded_by == user.id,
            )
        )
        .distinct()
        .all()
    )

    excel_docs = [d for d in all_authorized_docs if d.file_type == FileType.excel]
    non_excel_exist = any(d.file_type != FileType.excel for d in all_authorized_docs)

    # ------------------------------------------------------------------
    # 3. Qdrant semantic search (non-Excel)
    # ------------------------------------------------------------------
    qdrant_results: list[dict] = []
    if non_excel_exist:
        collection_name = f"tenant_{tenant_id}"
        try:
            # Search with role-based filter for shared docs
            search_role_ids = [role_id]
            # Also include user_id so private docs (which store user_id
            # as a role_id surrogate) are found
            search_role_ids.append(str(user.id))

            qdrant_results = search_vectors(
                collection_name=collection_name,
                query_vector=query_vector,
                role_ids=search_role_ids,
                limit=5,
            )
        except Exception as exc:
            logger.error("Qdrant search failed: %s", exc)

    # Build a lookup of document_id → filename
    doc_id_to_filename: dict[str, str] = {}
    for doc in all_authorized_docs:
        doc_id_to_filename[str(doc.id)] = doc.filename

    # Filter out any orphaned Qdrant vectors (e.g. from deleted documents)
    valid_qdrant_results = []
    for hit in qdrant_results:
        payload = hit.get("payload", {})
        if payload.get("document_id") in doc_id_to_filename:
            valid_qdrant_results.append(hit)
    qdrant_results = valid_qdrant_results

    # ------------------------------------------------------------------
    # 4. Excel pipeline
    # ------------------------------------------------------------------
    excel_results: list[dict] = []
    for doc in excel_docs:
        if not doc.excel_schema:
            continue
        try:
            abs_path = get_absolute_path(doc.file_path)
            result = execute_excel_query(abs_path, doc.excel_schema, query)
            print("###  16 \n")
            if result is not None:
                excel_results.append({
                    "filename": doc.filename,
                    "document_id": str(doc.id),
                    "result": result,
                })
            print("###  17 \n")
        except Exception as exc:
            logger.warning("Excel query failed for %s: %s", doc.filename, exc)

    # ------------------------------------------------------------------
    # 5. Build context block
    # ------------------------------------------------------------------
    context_parts: list[str] = []

    if qdrant_results:
        context_parts.append("[Document Chunks]")
        for hit in qdrant_results:
            payload = hit.get("payload", {})
            filename = doc_id_to_filename.get(payload.get("document_id", ""), "Unknown")
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

            context_parts.append(
                f"Source: {filename}{location_str} | Chunk: {chunk_idx}\n{chunk_text}"
            )
            context_parts.append("---")

    if excel_results:
        context_parts.append("[Excel Data Results]")
        for er in excel_results:
            context_parts.append(f"Source: {er['filename']}\nQuery: {query}\nResult: {er['result']}")
            context_parts.append("---")

    context_block = "\n".join(context_parts) if context_parts else "No relevant context found."

    print("############################### Context block: ", context_block)

    # ------------------------------------------------------------------
    # 6. Call Gemini for the final answer
    # ------------------------------------------------------------------
    final_prompt = f"""{_SYSTEM_PROMPT}

Context:
{context_block}

Conversation History (recent messages):
{conversation_history if conversation_history else "No previous messages."}

User Question: {query}

Answer:"""

    print("############################### Final prompt: ", final_prompt)
    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=final_prompt,
        )
        answer = (response.text or "").strip()
        if not answer:
            answer = "I could not generate an answer. Please try rephrasing your question."
    except Exception as exc:
        logger.error("Gemini answer generation failed: %s", exc)
        answer = "I encountered an error while generating an answer. Please try again."

    # ------------------------------------------------------------------
    # 7. Build citations list
    # ------------------------------------------------------------------
    citations: list[dict] = []
    for hit in qdrant_results:
        payload = hit.get("payload", {})
        doc_id = payload.get("document_id", "")
        citations.append({
            "document_id": doc_id,
            "filename": doc_id_to_filename.get(doc_id, "Unknown"),
            "chunk_text": payload.get("chunk_text", ""),
            "page_number": payload.get("page_number"),
            "slide_number": payload.get("slide_number"),
            "chunk_index": payload.get("chunk_index", 0),
        })

    return {
        "answer": answer,
        "citations": citations,
    }
