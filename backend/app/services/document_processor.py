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
from app.models.enums import DocumentStatus, FileType
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


def _get_pptx_slide_text(slide) -> str:
    """Extract all text from a single slide's shapes (titles, text boxes, tables, notes)."""
    texts = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                line = "".join(run.text for run in para.runs).strip()
                if line:
                    texts.append(line)
        # Tables
        if shape.has_table:
            for row in shape.table.rows:
                row_text = " | ".join(
                    cell.text.strip() for cell in row.cells if cell.text.strip()
                )
                if row_text:
                    texts.append(row_text)
    # Speaker notes
    if slide.has_notes_slide:
        notes_text = slide.notes_slide.notes_text_frame.text.strip()
        if notes_text:
            texts.append(f"[Speaker Notes] {notes_text}")
    return "\n".join(texts)


def extract_text_from_pptx(file_path: str) -> list[dict]:
    """
    Extract text and vision descriptions from each slide of a PPTX file.

    For each slide:
      1. Extract text from all shapes and notes using python-pptx.
      2. Merge extracted text with the vision description from Gemini.
      3. If merged text > 2000 tokens (approx), split into two chunks.

    A single Gemini API call is made for the entire file via
    describe_pptx_slides to get visual descriptions for all slides.

    Returns a list of dicts: {"text": "...", "slide_number": N, "slide_title": "..."}
    """
    prs = Presentation(file_path)

    # Get visual descriptions for all slides in one API call
    visual_descriptions = embedding_service.describe_pptx_slides(file_path)

    results = []
    for slide_idx, slide in enumerate(prs.slides, start=1):
        # Slide title
        slide_title = ""
        if slide.shapes.title and slide.shapes.title.text:
            slide_title = slide.shapes.title.text.strip()

        # Extracted text
        extracted_text = _get_pptx_slide_text(slide)

        # Merge with vision description
        vision_description = visual_descriptions.get(slide_idx, "")
        merged = extracted_text
        if vision_description:
            merged = extracted_text + "\n\n" + vision_description

        merged = merged.strip()
        if not merged:
            continue

        # Approximate token count: word_count * 1.3
        approx_tokens = len(merged.split()) * 1.3
        if approx_tokens > 2000 and len(merged) > 1:
            mid = len(merged) // 2
            results.append({"text": merged[:mid], "slide_number": slide_idx, "slide_title": slide_title})
            results.append({"text": merged[mid:], "slide_number": slide_idx, "slide_title": slide_title})
        else:
            results.append({"text": merged, "slide_number": slide_idx, "slide_title": slide_title})

    return results


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
                    },
                })
                chunk_index += 1

        elif file_type == FileType.pptx:
            slides = extract_text_from_pptx(abs_file_path)
            for slide in slides:
                if not slide["text"].strip():
                    continue
                vector = embedding_service.embed_text(slide["text"])
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
