"""
Document processing pipeline: extracts text, chunks it, generates embeddings,
and stores vectors in Qdrant.
"""
import os
import uuid
import logging

import fitz  # PyMuPDF
import docx as python_docx
import pandas as pd
from pptx import Presentation
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.enums import DocumentStatus, FileType, Visibility
from app.services import embedding_service, qdrant_service

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


# ---------------------------------------------------------------------------
# Text extractors
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: str) -> list[dict]:
    """
    Extract text page-by-page from a PDF file using PyMuPDF.

    Returns a list of dicts: {"text": "...", "page_number": N}
    Pages with no extractable text are skipped.
    """
    pages = []
    doc = fitz.open(file_path)
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if text:
            pages.append({"text": text, "page_number": page_num})
    doc.close()
    return pages


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract all paragraph text from a DOCX file using python-docx.

    Returns the full document text as a single newline-joined string.
    """
    document = python_docx.Document(file_path)
    paragraphs = [para.text for para in document.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)


def extract_text_from_txt(file_path: str) -> str:
    """Read and return the full content of a plain-text file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()



def extract_excel_schema(file_path: str) -> dict:
    """
    Read an Excel file with pandas and return a schema dict containing:
    columns, dtypes, shape, and 3 sample rows.
    """
    df = pd.read_excel(file_path, engine="openpyxl")
    return {
        "columns": df.columns.tolist(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "sample": df.head(3).to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Text chunker
# ---------------------------------------------------------------------------

def chunk_text(text: str) -> list[str]:
    """
    Split text into chunks using RecursiveCharacterTextSplitter.

    chunk_size=1000, chunk_overlap=200
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_text(text)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_document(document_id: str, db: Session) -> None:
    """
    Main ingestion pipeline for a document.

    1. Fetches the document record by ID.
    2. Sets status → processing.
    3. Extracts text / schema based on file_type.
    4. Chunks, embeds, and upserts into Qdrant (except Excel).
    5. Sets status → ready on success, or → failed on any exception.
    """
    document: Document | None = db.query(Document).filter(
        Document.id == document_id
    ).first()

    if not document:
        logger.error("process_document: document %s not found", document_id)
        return

    try:
        # Set status to processing
        document.status = DocumentStatus.processing
        db.commit()

        # Fetch role_ids from access policies
        policies = (
            db.query(DocumentAccessPolicy)
            .filter(DocumentAccessPolicy.document_id == document.id)
            .all()
        )
        role_ids = [str(policy.role_id) for policy in policies]

        # For private documents with no access policies, store the uploader's
        # user_id as a surrogate role_id so the RAG search can find them
        if not role_ids and document.visibility == Visibility.private:
            role_ids = [str(document.uploaded_by)]

        tenant_id = str(document.tenant_id)
        doc_id = str(document.id)
        file_type = document.file_type

        # Get or create Qdrant collection
        collection_name = qdrant_service.get_or_create_tenant_collection(tenant_id)

        from app.services.storage_service import get_absolute_path
        abs_file_path = get_absolute_path(document.file_path)

        points: list[dict] = []
        chunk_index = 0

        if file_type == FileType.pdf:
            pages = extract_text_from_pdf(abs_file_path)
            for page in pages:
                chunks = chunk_text(page["text"])
                for chunk in chunks:
                    vector = embedding_service.embed_text(chunk)
                    points.append({
                        "id": str(uuid.uuid4()),
                        "vector": vector,
                        "payload": {
                            "document_id": doc_id,
                            "tenant_id": tenant_id,
                            "role_ids": role_ids,
                            "file_type": "pdf",
                            "chunk_index": chunk_index,
                            "page_number": page["page_number"],
                            "chunk_text": chunk,
                        },
                    })
                    chunk_index += 1

        elif file_type == FileType.docx:
            full_text = extract_text_from_docx(abs_file_path)
            chunks = chunk_text(full_text)
            for chunk in chunks:
                vector = embedding_service.embed_text(chunk)
                points.append({
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "document_id": doc_id,
                        "tenant_id": tenant_id,
                        "role_ids": role_ids,
                        "file_type": "docx",
                        "chunk_index": chunk_index,
                        "page_number": None,
                        "chunk_text": chunk,
                    },
                })
                chunk_index += 1

        elif file_type == FileType.text:
            full_text = extract_text_from_txt(abs_file_path)
            chunks = chunk_text(full_text)
            for chunk in chunks:
                vector = embedding_service.embed_text(chunk)
                points.append({
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "document_id": doc_id,
                        "tenant_id": tenant_id,
                        "role_ids": role_ids,
                        "file_type": "text",
                        "chunk_index": chunk_index,
                        "page_number": None,
                        "chunk_text": chunk,
                    },
                })
                chunk_index += 1

        elif file_type == FileType.pptx:
            slides = embedding_service.process_pptx_slides(abs_file_path)
            for slide in slides:
                vector = slide["vector"]
                points.append({
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "document_id": doc_id,
                        "tenant_id": tenant_id,
                        "role_ids": role_ids,
                        "file_type": "pptx",
                        "chunk_index": chunk_index,
                        "slide_number": slide["slide_number"],
                        "slide_title": slide["slide_title"],
                        "chunk_text": slide["text"],
                    },
                })
                chunk_index += 1

        elif file_type == FileType.audio:
            transcription = embedding_service.transcribe_audio(abs_file_path)
            chunks = chunk_text(transcription)
            for chunk in chunks:
                vector = embedding_service.embed_text(chunk)
                points.append({
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "document_id": doc_id,
                        "tenant_id": tenant_id,
                        "role_ids": role_ids,
                        "file_type": "audio",
                        "chunk_index": chunk_index,
                        "page_number": None,
                        "chunk_text": chunk,
                    },
                })
                chunk_index += 1

        elif file_type == FileType.excel:
            schema = extract_excel_schema(abs_file_path)
            document.excel_schema = schema
            document.chunk_count = 0
            document.status = DocumentStatus.ready
            db.commit()
            logger.info("Excel document %s processed (schema only, no vectors)", doc_id)
            return

        # Upsert all points into Qdrant
        if points:
            qdrant_service.upsert_vectors(collection_name, points)

        document.chunk_count = chunk_index
        document.status = DocumentStatus.ready
        db.commit()
        logger.info(
            "Document %s processed: %d chunks upserted into %s",
            doc_id,
            chunk_index,
            collection_name,
        )

    except Exception as exc:
        logger.error("Failed to process document %s: %s", document_id, exc, exc_info=True)
        try:
            document.status = DocumentStatus.failed
            db.commit()
        except Exception:
            db.rollback()
