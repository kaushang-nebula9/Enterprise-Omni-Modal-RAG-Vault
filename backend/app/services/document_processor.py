"""
Document processing pipeline: extracts text, chunks it, generates embeddings,
and stores vectors in Qdrant.
"""
import os
import uuid
import logging
import json
import zipfile

import fitz  # PyMuPDF
import pymupdf4llm
import pymupdf  # alias for fitz (PyMuPDF)
import docx as python_docx
from docx.oxml.ns import qn
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
# Gemini Vision helper (used by both PDF and DOCX pipelines)
# ---------------------------------------------------------------------------

def describe_slide_image(image_path: str) -> str:
    """
    Send a local image file to Gemini Vision and return a detailed description.

    This mirrors the inline Gemini Vision call used in the PPTX pipeline
    inside embedding_service and is placed here so the PDF and DOCX pipelines
    can call it without depending on additional files.

    Returns an empty string if the call fails.
    """
    import time
    from google import genai
    from google.genai import types as genai_types
    from app.core.config import settings

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        ext = image_path.rsplit(".", 1)[-1].lower()
        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "webp": "image/webp",
        }
        mime_type = mime_map.get(ext, "image/png")

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[
                genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                "Describe this image in detail. Be specific about data, trends, and key takeaways.",
            ],
        )
        time.sleep(0.5)  # avoid rate limits
        return (response.text or "").strip()
    except Exception as exc:
        logger.error("describe_slide_image: failed to describe image '%s': %s", image_path, exc)
        return ""


# ---------------------------------------------------------------------------
# Text extractors
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: str, document_id: str) -> list[dict]:
    """
    Extract text, tables, and embedded images page-by-page from a PDF file.

    Uses pymupdf4llm to produce clean Markdown per page, then queries each
    page for raster images and sends qualifying images to Gemini Vision for
    description.  Small decorative images (< 100×100 px) are skipped.

    Returns a list of dicts: {"text": "...", "page_number": N}
    Pages with no extractable content after merging are skipped.
    """
    results = []
    doc = fitz.open(file_path)

    for page_index in range(len(doc)):
        page = doc[page_index]

        # ── 1. Extract Markdown via pymupdf4llm ──────────────────────────────
        page_markdown = pymupdf4llm.to_markdown(doc, pages=[page_index])
        print("#################")
        print(f"PDF PAGE {page_index + 1} - PyMuPDF4LLM extracted Markdown: ", page_markdown, "\n")

        # ── 2. Embedded image discovery ───────────────────────────────────────
        image_list = page.get_images(full=True)
        print("#################")
        print(f"PDF PAGE {page_index + 1} - Number of embedded images found: ", len(image_list), "\n")

        image_descriptions: list[str] = []

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                pix = pymupdf.Pixmap(doc, xref)

                # Convert CMYK (> 4 channels) to RGB
                if pix.n > 4:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)

                # Skip tiny decorative images
                if pix.width < 100 or pix.height < 100:
                    print("#################")
                    print(
                        f"PDF PAGE {page_index + 1} - Skipping small decorative image (too small): ",
                        pix.width,
                        "x",
                        pix.height,
                        "\n",
                    )
                    continue

                # Save to /tmp for Gemini Vision
                temp_image_path = f"/tmp/{document_id}_page{page_index}_img{img_index}.png"
                pix.save(temp_image_path)

                print("#################")
                print(
                    f"PDF PAGE {page_index + 1} - Sending image to Gemini Vision: ",
                    temp_image_path,
                    "\n",
                )

                try:
                    image_description = describe_slide_image(temp_image_path)
                    print("#################")
                    print(
                        f"PDF PAGE {page_index + 1} - Gemini Vision description: ",
                        image_description,
                        "\n",
                    )
                    if image_description:
                        image_descriptions.append(f"[Visual Content: {image_description}]")
                except Exception as vision_exc:
                    logger.error(
                        "PDF PAGE %d - Gemini Vision call failed for image %d: %s",
                        page_index + 1,
                        img_index,
                        vision_exc,
                    )
                    print("#################")
                    print(
                        f"PDF PAGE {page_index + 1} - Gemini Vision call failed for image {img_index}: ",
                        vision_exc,
                        "\n",
                    )
                finally:
                    # Always clean up temp file
                    if os.path.exists(temp_image_path):
                        os.remove(temp_image_path)

            except Exception as img_exc:
                logger.error(
                    "PDF PAGE %d - Failed to process image xref %d: %s",
                    page_index + 1,
                    xref,
                    img_exc,
                )
                print("#################")
                print(
                    f"PDF PAGE {page_index + 1} - Failed to process image xref {xref}: ",
                    img_exc,
                    "\n",
                )

        # ── 3. Merge Markdown + image descriptions ────────────────────────────
        parts = [page_markdown] + [f"\n\n{desc}" for desc in image_descriptions]
        merged_content = "".join(parts)

        print("#################")
        print(f"PDF PAGE {page_index + 1} - Final merged content: ", merged_content, "\n")

        # ── 4. Skip empty pages ───────────────────────────────────────────────
        if not merged_content.strip():
            print("#################")
            print(f"PDF PAGE {page_index + 1} - Skipping empty page\n")
            continue

        results.append({"text": merged_content, "page_number": page_index + 1})

    doc.close()

    print("#################")
    print("PDF EXTRACTION COMPLETE - Total pages extracted: ", len(results), "\n")

    return results


def extract_text_from_docx(file_path: str, document_id: str) -> str:
    """
    Extract all text, tables, and embedded images from a DOCX file.

    Text and tables are traversed in document order via the XML body.
    Tables are rendered as Markdown tables.  Images are extracted from the
    ZIP archive inside the DOCX and described by Gemini Vision.

    Returns the full merged content as a single string.
    """
    doc = python_docx.Document(file_path)

    # ── 1. Text and table extraction (document order) ─────────────────────────
    print("#################")
    print("DOCX EXTRACTION - Starting text and table extraction\n")

    text_parts: list[str] = []

    heading_prefix_map = {
        "heading 1": "#",
        "heading 2": "##",
        "heading 3": "###",
        "heading 4": "####",
        "heading 5": "#####",
        "heading 6": "######",
    }

    for child in doc.element.body:
        if child.tag == qn("w:p"):
            # ── Paragraph ──────────────────────────────────────────────────
            para = python_docx.text.paragraph.Paragraph(child, doc)
            para_text = para.text.strip()
            if not para_text:
                continue

            style_name = (para.style.name or "").lower() if para.style else ""
            if style_name.startswith("heading"):
                prefix = heading_prefix_map.get(style_name, "#")
                text_parts.append(f"{prefix} {para_text}")
            else:
                text_parts.append(para_text)

        elif child.tag == qn("w:tbl"):
            # ── Table ──────────────────────────────────────────────────────
            table = python_docx.table.Table(child, doc)
            rows = table.rows
            if not rows:
                continue

            md_rows: list[str] = []
            for row_idx, row in enumerate(rows):
                cells = [cell.text.strip() for cell in row.cells]
                md_rows.append("| " + " | ".join(cells) + " |")
                if row_idx == 0:
                    # Add separator after header row
                    md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")

            text_parts.append("\n".join(md_rows))

    extracted_text_and_tables = "\n\n".join(text_parts)

    print("#################")
    print("DOCX EXTRACTION - Extracted text and tables: ", extracted_text_and_tables, "\n")

    # ── 2. Image extraction from ZIP archive ──────────────────────────────────
    print("#################")
    print("DOCX EXTRACTION - Opening ZIP archive to find media files\n")

    image_descriptions: list[str] = []
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

    with zipfile.ZipFile(file_path, "r") as z:
        media_files = [f for f in z.namelist() if f.startswith("word/media/")]

    print("#################")
    print("DOCX EXTRACTION - Media files found in word/media/: ", media_files, "\n")

    with zipfile.ZipFile(file_path, "r") as z:
        for index, media_file in enumerate(media_files):
            ext = os.path.splitext(media_file)[1].lower()

            if ext not in image_extensions:
                print("#################")
                print("DOCX EXTRACTION - Skipping non-image media file: ", media_file, "\n")
                continue

            temp_image_path = f"/tmp/{document_id}_img_{index}{ext}"

            try:
                with z.open(media_file) as img_data:
                    with open(temp_image_path, "wb") as tmp_f:
                        tmp_f.write(img_data.read())

                print("#################")
                print("DOCX EXTRACTION - Sending image to Gemini Vision: ", temp_image_path, "\n")

                try:
                    image_description = describe_slide_image(temp_image_path)
                    print("#################")
                    print("DOCX EXTRACTION - Gemini Vision description: ", image_description, "\n")
                    if image_description:
                        image_descriptions.append(f"[Visual Content: {image_description}]")
                except Exception as vision_exc:
                    logger.error(
                        "DOCX EXTRACTION - Gemini Vision call failed for '%s': %s",
                        media_file,
                        vision_exc,
                    )
                    print("#################")
                    print(
                        "DOCX EXTRACTION - Gemini Vision call failed for: ",
                        media_file,
                        " Error: ",
                        vision_exc,
                        "\n",
                    )
            except Exception as extract_exc:
                logger.error(
                    "DOCX EXTRACTION - Failed to extract media file '%s': %s",
                    media_file,
                    extract_exc,
                )
                print("#################")
                print(
                    "DOCX EXTRACTION - Failed to extract media file: ",
                    media_file,
                    " Error: ",
                    extract_exc,
                    "\n",
                )
            finally:
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)

    # ── 3. Merge text + tables + image descriptions ────────────────────────────
    all_parts = [extracted_text_and_tables] + [f"\n\n{desc}" for desc in image_descriptions]
    final_merged_content = "".join(all_parts)

    print("#################")
    print("DOCX EXTRACTION - Final merged content (text + tables + images): ", final_merged_content, "\n")

    return final_merged_content


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
    
    total_rows = int(df.shape[0])
    total_cols = int(df.shape[1])
    
    # Use pandas to_json which correctly maps NaNs/NaTs to valid JSON 'null',
    # then load it back as a dict to be safely stored in the JSONB column.
    sample_json = df.head(3).to_json(orient="records", date_format="iso")
    sample_records = json.loads(sample_json)
    
    return {
        "columns": df.columns.tolist(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "shape": {"rows": total_rows, "columns": total_cols},
        "sample": sample_records,
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

        # Always add the uploader's user_id as a surrogate role_id
        # so the uploader can always query their own documents via RAG.
        uploader_id = str(document.uploaded_by)
        if uploader_id not in role_ids:
            role_ids.append(uploader_id)

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
            print("#################")
            print("Starting PDF pipeline for document: ", document.filename, "\n")

            pages = extract_text_from_pdf(abs_file_path, doc_id)
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

            total_chunk_count = chunk_index
            print("#################")
            print("PDF pipeline complete - Total chunks embedded and stored in Qdrant: ", total_chunk_count, "\n")

        elif file_type == FileType.docx:
            print("#################")
            print("Starting DOCX pipeline for document: ", document.filename, "\n")

            full_text = extract_text_from_docx(abs_file_path, doc_id)
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

            total_chunk_count = chunk_index
            print("#################")
            print("DOCX pipeline complete - Total chunks embedded and stored in Qdrant: ", total_chunk_count, "\n")

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
