"""
Document processing pipeline: extracts text, chunks it, generates embeddings,
and stores vectors in Qdrant.
"""

import os
import uuid
import logging
import json
import zipfile
from typing import Optional

import fitz  # PyMuPDF
import pymupdf4llm
import pymupdf
import docx as python_docx
from docx.oxml.ns import qn
import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from fastapi import UploadFile
import magic
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.enums import (
    DocumentStatus,
    FileType,
    EXTENSION_TO_FILE_TYPE,
    TABULAR_FILE_TYPES,
)
from app.services import embedding_service, qdrant_service

logger = logging.getLogger(__name__)

# Namespace UUID for deterministic point-ID generation via uuid5.
# This ensures that retried Celery tasks produce the same point IDs
# and Qdrant upsert remains idempotent per chunk.
NAMESPACE_DOC = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Maps MIME types detected at upload time to their corresponding FileType enum value
MIME_TO_FILE_TYPE: dict[str, FileType] = {
    "application/pdf": FileType.pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.docx,
    "text/plain": FileType.text,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": FileType.pptx,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.excel,
    "application/vnd.ms-excel": FileType.xls,
    "application/CDFV2": FileType.xls,
    "application/x-cfb": FileType.xls,
    "application/vnd.ms-excel.sheet.macroEnabled.12": FileType.xlsm,
    "application/vnd.ms-excel.sheet.binary.macroEnabled.12": FileType.xlsb,
    "application/vnd.oasis.opendocument.spreadsheet": FileType.ods,
    "text/csv": FileType.csv,
    "text/tab-separated-values": FileType.tsv,
    "audio/mpeg": FileType.audio,
    "audio/mp3": FileType.audio,
    "audio/wav": FileType.audio,
    "audio/x-wav": FileType.audio,
    "audio/x-m4a": FileType.audio,
    "audio/m4a": FileType.audio,
    "audio/mp4": FileType.audio,
    "audio/x-mp4": FileType.audio,
}


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


def is_mime_compatible(ext_file_type: FileType, mime_type: str) -> bool:
    detected_type = MIME_TO_FILE_TYPE.get(mime_type)
    if detected_type == ext_file_type:
        return True

    # Allow compatibility between any of the Excel OpenXML MIME types and extensions
    openxml_excel_mimes = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel.sheet.macroEnabled.12",
        "application/vnd.ms-excel.sheet.binary.macroEnabled.12",
    }
    if mime_type in openxml_excel_mimes and ext_file_type in (
        FileType.excel,
        FileType.xlsm,
        FileType.xlsb,
    ):
        return True

    if mime_type == "text/plain" and ext_file_type in (
        FileType.text,
        FileType.csv,
        FileType.tsv,
    ):
        return True
    if mime_type == "application/octet-stream" and ext_file_type == FileType.xlsb:
        return True
    if mime_type == "application/zip" and ext_file_type in (
        FileType.docx,
        FileType.pptx,
        FileType.excel,
        FileType.xlsm,
        FileType.ods,
    ):
        return True

    return False


def validate_upload_file(file: UploadFile) -> FileType:
    """
    Validate the file using both its extension and its MIME type (via python-magic).
    Returns the mapped FileType if valid, otherwise raises HTTPException.
    """
    from fastapi import HTTPException, status

    # Resolve the FileType from the file extension
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ext_file_type = EXTENSION_TO_FILE_TYPE.get(ext)
    if not ext_file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension: {ext}",
        )

    # Read the first 2048 bytes to detect the real MIME type
    try:
        first_bytes = file.file.read(2048)
        file.file.seek(0)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file for validation: {str(e)}",
        )

    try:
        mime_type = magic.from_buffer(first_bytes, mime=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to detect file MIME type: {str(e)}",
        )

    # Reject the file if the extension and detected MIME type do not match
    if not is_mime_compatible(ext_file_type, mime_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' does not match detected MIME type '{mime_type}'",
        )

    return ext_file_type


# ---------------------------------------------------------------------------
# Image description helper (used by PDF, DOCX, and PPTX pipelines)
# ---------------------------------------------------------------------------


def describe_slide_image(image_path: str) -> str:
    """
    Send a local image file to Claude Vision and return a detailed description.
    Returns an empty string if the call fails.
    """
    import base64
    from anthropic import Anthropic
    from app.core.config import settings

    try:
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Resolve the correct MIME type for the image before sending to Claude
        ext = image_path.rsplit(".", 1)[-1].lower()
        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        mime_type = mime_map.get(ext, "image/png")

        # Read and base64-encode the image for the API payload
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        system_prompt = "If the image is a chart or a graph, then give exact values and analyze the data in a structured format."

        # Send the image to Claude Vision and return the description
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64_image,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Describe this image in detail. Be specific about data, trends, and key takeaways.",
                        },
                    ],
                }
            ],
        )
        return message.content[0].text.strip()
    except Exception as exc:
        logger.error(
            "describe_slide_image: failed to describe image '%s': %s",
            image_path,
            exc,
        )
        return ""


# ---------------------------------------------------------------------------
# Text extractor functions for PDF, DOCX, and TXT files
# ---------------------------------------------------------------------------


def extract_text_from_pdf(file_path: str, document_id: str) -> list[dict]:
    """
    Extract text, tables, and embedded images page-by-page from a PDF file.

    Uses pymupdf4llm to produce clean Markdown per page, then queries each
    page for raster images and sends qualifying images to Claude Vision for
    description. Small decorative images (< 100x100 px) are skipped.

    Returns a list of dicts: {"text": "...", "page_number": N}
    Pages with no extractable content after merging are skipped.
    """
    results = []
    doc = fitz.open(file_path)

    for page_index in range(len(doc)):
        page = doc[page_index]

        # 1. Extract Markdown text and tables via pymupdf4llm
        page_markdown = pymupdf4llm.to_markdown(doc, pages=[page_index])

        # 2. Find and describe embedded images on this page
        image_descriptions: list[str] = []
        for img_index, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            try:
                pix = pymupdf.Pixmap(doc, xref)
                if pix.n > 4:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)  # convert CMYK to RGB

                if pix.width < 100 or pix.height < 100:
                    continue  # skip small decorative images

                temp_image_path = (
                    f"/tmp/{document_id}_page{page_index}_img{img_index}.png"
                )
                pix.save(temp_image_path)

                try:
                    image_description = describe_slide_image(temp_image_path)
                    if image_description:
                        image_descriptions.append(
                            f"[Visual Content: {image_description}]"
                        )
                except Exception as vision_exc:
                    logger.error(
                        "PDF page %d - vision call failed for image %d: %s",
                        page_index + 1,
                        img_index,
                        vision_exc,
                    )
                finally:
                    if os.path.exists(temp_image_path):
                        os.remove(temp_image_path)

            except Exception as img_exc:
                logger.error(
                    "PDF page %d - failed to process image xref %d: %s",
                    page_index + 1,
                    xref,
                    img_exc,
                )

        # 3. Merge page text with image descriptions and skip if nothing was extracted
        parts = [page_markdown] + [f"\n\n{desc}" for desc in image_descriptions]
        merged_content = "".join(parts)

        if not merged_content.strip():
            continue

        results.append({"text": merged_content, "page_number": page_index + 1})

    doc.close()
    return results


def extract_text_from_docx(file_path: str, document_id: str) -> str:
    """
    Extract all text, tables, and embedded images from a DOCX file.

    Text and tables are traversed in document order via the XML body.
    Tables are rendered as Markdown tables. Images are extracted from the
    ZIP archive inside the DOCX and described by Claude Vision.

    Returns the full merged content as a single string.
    """
    doc = python_docx.Document(file_path)

    heading_prefix_map = {
        "heading 1": "#",
        "heading 2": "##",
        "heading 3": "###",
        "heading 4": "####",
        "heading 5": "#####",
        "heading 6": "######",
    }

    # 1. Walk the document body in order and extract paragraphs and tables as Markdown
    text_parts: list[str] = []
    for child in doc.element.body:
        if child.tag == qn("w:p"):
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
            table = python_docx.table.Table(child, doc)
            if not table.rows:
                continue
            md_rows: list[str] = []
            for row_idx, row in enumerate(table.rows):
                cells = [cell.text.strip() for cell in row.cells]
                md_rows.append("| " + " | ".join(cells) + " |")
                if row_idx == 0:
                    md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
            text_parts.append("\n".join(md_rows))

    extracted_text_and_tables = "\n\n".join(text_parts)

    # 2. Extract and describe images from the DOCX ZIP archive
    image_descriptions: list[str] = []
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

    with zipfile.ZipFile(file_path, "r") as z:
        media_files = [f for f in z.namelist() if f.startswith("word/media/")]

    with zipfile.ZipFile(file_path, "r") as z:
        for index, media_file in enumerate(media_files):
            ext = os.path.splitext(media_file)[1].lower()
            if ext not in image_extensions:
                continue

            temp_image_path = f"/tmp/{document_id}_img_{index}{ext}"
            try:
                with z.open(media_file) as img_data:
                    with open(temp_image_path, "wb") as tmp_f:
                        tmp_f.write(img_data.read())

                image_description = describe_slide_image(temp_image_path)
                if image_description:
                    image_descriptions.append(f"[Visual Content: {image_description}]")
            except Exception as exc:
                logger.error(
                    "DOCX extraction - failed to process '%s': %s", media_file, exc
                )
            finally:
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)

    # 3. Merge text, tables, and image descriptions into a single string
    all_parts = [extracted_text_and_tables] + [
        f"\n\n{desc}" for desc in image_descriptions
    ]
    return "".join(all_parts)


def extract_text_from_txt(file_path: str) -> str:
    """Read and return the full content of a plain-text file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def load_dataframe(file_path: str, file_type: FileType) -> pd.DataFrame:
    """Load a DataFrame from a file based on its FileType."""
    if file_type == FileType.csv:
        try:
            return pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8")
        except Exception:
            return pd.read_csv(file_path, sep=None, engine="python", encoding="latin-1")
    elif file_type == FileType.tsv:
        try:
            return pd.read_csv(file_path, sep="\t", engine="python", encoding="utf-8")
        except Exception:
            return pd.read_csv(file_path, sep="\t", engine="python", encoding="latin-1")
    elif file_type == FileType.excel:
        return pd.read_excel(file_path, engine="openpyxl")
    elif file_type == FileType.xlsm:
        return pd.read_excel(file_path, engine="openpyxl")  # macros ignored
    elif file_type == FileType.xls:
        return pd.read_excel(file_path, engine="xlrd")
    elif file_type == FileType.xlsb:
        return pd.read_excel(file_path, engine="pyxlsb")
    elif file_type == FileType.ods:
        return pd.read_excel(file_path, engine="odf")
    else:
        raise ValueError(f"Unsupported file type for DataFrame loading: {file_type}")


def extract_excel_schema(file_path: str, file_type: Optional[FileType] = None) -> dict:
    """
    Read an Excel, CSV, or other tabular/spreadsheet file with pandas and return a schema dict
    containing: columns, dtypes, shape, and 3 sample rows.
    """
    if file_type is None:
        ext = "." + file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        file_type = EXTENSION_TO_FILE_TYPE.get(ext)
        if not file_type:
            raise ValueError(f"Unsupported file extension: {ext}")

    # Load the file into a DataFrame and extract shape and sample rows
    df = load_dataframe(file_path, file_type)

    total_rows = int(df.shape[0])
    total_cols = int(df.shape[1])

    # Use pandas to_json to correctly map NaNs/NaTs to valid JSON null,
    # then reload as a dict for safe storage in the JSONB column.
    sample_json = df.head(3).to_json(orient="records", date_format="iso")
    sample_records = json.loads(sample_json)

    print("#################")
    print(
        f"Extracted schema for {file_path}: {total_rows} rows, {total_cols} columns, sample: {sample_records}"
    )

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
    """Split text into chunks using RecursiveCharacterTextSplitter (size=1000, overlap=200)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_text(text)


# ---------------------------------------------------------------------------
# Qdrant point builder
# ---------------------------------------------------------------------------


def build_vector_point(
    doc_id: str,
    tenant_id: str,
    role_ids: list[str],
    chunk_index: int,
    chunk: str,
    file_type: str,
    page_number: Optional[int] = None,
    slide_number: Optional[int] = None,
    slide_title: Optional[str] = None,
) -> dict:
    """
    Embed a text chunk and return a Qdrant point dict ready for upsert.
    page_number, slide_number, and slide_title are included only when provided.
    """
    # Generate dense and sparse vectors for the chunk
    vector = embedding_service.embed_text(chunk)
    sparse_vector = qdrant_service.generate_sparse_vector(chunk)
    point_id = str(uuid.uuid5(NAMESPACE_DOC, f"{doc_id}_chunk_{chunk_index}"))

    # Build the base payload, then attach optional positional metadata
    payload = {
        "document_id": doc_id,
        "tenant_id": tenant_id,
        "role_ids": role_ids,
        "file_type": file_type,
        "chunk_index": chunk_index,
        "chunk_text": chunk,
    }

    if page_number is not None:
        payload["page_number"] = page_number
    if slide_number is not None:
        payload["slide_number"] = slide_number
    if slide_title is not None:
        payload["slide_title"] = slide_title

    return {
        "id": point_id,
        "dense_vector": vector,
        "sparse_vector": sparse_vector,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def process_document(document_id: str, db: Session) -> None:
    """
    Fetches the document record and marks it as processing.
    Collects the role IDs that are allowed to access this document.
    Extracts content based on file type - text, slides, transcript, or schema.
    Chunks and embeds the extracted text into vector points.
    Tabular files skip vectorization and store only their schema.
    Upserts all vector points into the tenant's Qdrant collection.
    Generates a short AI description of the document content.
    Sets status to ready on success, or failed on any exception.
    """
    document: Document | None = (
        db.query(Document).filter(Document.id == document_id).first()
    )

    if not document:
        logger.error("process_document: document %s not found", document_id)
        return

    try:
        # Mark document as processing
        document.status = DocumentStatus.processing
        db.commit()

        # Build the list of role IDs that are allowed to access this document
        policies = (
            db.query(DocumentAccessPolicy)
            .filter(DocumentAccessPolicy.document_id == document.id)
            .all()
        )
        role_ids = [str(policy.role_id) for policy in policies]

        uploader_id = str(document.uploaded_by)
        if uploader_id not in role_ids:
            role_ids.append(uploader_id)

        tenant_id = str(document.tenant_id)
        doc_id = str(document.id)
        file_type = document.file_type

        # Get or create the Qdrant collection for this tenant
        collection_name = qdrant_service.get_or_create_tenant_collection(tenant_id)

        from app.services.storage_service import get_absolute_path

        abs_file_path = get_absolute_path(document.file_path)

        points: list[dict] = []
        chunk_index = 0
        content_sample = ""

        if file_type == FileType.pdf:
            # Extract text and images per page, then chunk and embed each page
            pages = extract_text_from_pdf(abs_file_path, doc_id)
            combined_text = "\n".join(page["text"] for page in pages)
            content_sample = combined_text[:2000]

            for page in pages:
                for chunk in chunk_text(page["text"]):
                    points.append(
                        build_vector_point(
                            doc_id,
                            tenant_id,
                            role_ids,
                            chunk_index,
                            chunk,
                            file_type="pdf",
                            page_number=page["page_number"],
                        )
                    )
                    chunk_index += 1

        elif file_type == FileType.docx:
            # Extract text, tables, and images, then chunk and embed
            full_text = extract_text_from_docx(abs_file_path, doc_id)
            content_sample = full_text[:2000]

            for chunk in chunk_text(full_text):
                points.append(
                    build_vector_point(
                        doc_id,
                        tenant_id,
                        role_ids,
                        chunk_index,
                        chunk,
                        file_type="docx",
                    )
                )
                chunk_index += 1

        elif file_type == FileType.text:
            # Read the full file and chunk and embed it
            full_text = extract_text_from_txt(abs_file_path)
            content_sample = full_text[:2000]

            for chunk in chunk_text(full_text):
                points.append(
                    build_vector_point(
                        doc_id,
                        tenant_id,
                        role_ids,
                        chunk_index,
                        chunk,
                        file_type="text",
                    )
                )
                chunk_index += 1

        elif file_type == FileType.pptx:
            # process_pptx_slides handles both extraction and embedding per slide
            slides = embedding_service.process_pptx_slides(abs_file_path)
            combined_text = "\n".join(slide["text"] for slide in slides)
            content_sample = combined_text[:2000]

            for slide in slides:
                sparse_vector = qdrant_service.generate_sparse_vector(slide["text"])
                point_id = str(
                    uuid.uuid5(NAMESPACE_DOC, f"{doc_id}_chunk_{chunk_index}")
                )
                points.append(
                    {
                        "id": point_id,
                        "dense_vector": slide["vector"],
                        "sparse_vector": sparse_vector,
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
                    }
                )
                chunk_index += 1

        elif file_type == FileType.audio:
            # Transcribe audio to text, then chunk and embed the transcript
            transcription = embedding_service.transcribe_audio(abs_file_path)
            content_sample = transcription[:2000]

            for chunk in chunk_text(transcription):
                points.append(
                    build_vector_point(
                        doc_id,
                        tenant_id,
                        role_ids,
                        chunk_index,
                        chunk,
                        file_type="audio",
                    )
                )
                chunk_index += 1

        elif file_type in TABULAR_FILE_TYPES:
            # Tabular files are queried via Pandas at runtime, not chunked into Qdrant.
            # Only extract and store the schema so the query layer knows the structure.
            schema = extract_excel_schema(abs_file_path, file_type)
            document.excel_schema = schema
            document.chunk_count = 0
            document.status = DocumentStatus.ready
            db.commit()

            try:
                excel_sample = (
                    f"Columns: {schema['columns']}. Sample data: {schema['sample']}"
                )
                description = embedding_service.generate_document_description(
                    excel_sample, document.file_type.value
                )
                if description is not None:
                    document.description = description
                    db.commit()
            except Exception as desc_exc:
                logger.error(
                    "Failed to generate description for %s: %s",
                    document.file_type.value,
                    desc_exc,
                )

            logger.info(
                "%s document %s processed (schema only, no vectors)",
                document.file_type.value.capitalize(),
                doc_id,
            )
            return

        # Upsert all vector points into Qdrant and mark the document as ready
        if points:
            qdrant_service.upsert_vectors(collection_name, points)

        document.chunk_count = chunk_index
        document.status = DocumentStatus.ready
        db.commit()

        # Generate and save a short description of the document
        try:
            if content_sample:
                description = embedding_service.generate_document_description(
                    content_sample, document.file_type.value
                )
                if description is not None:
                    document.description = description
                    db.commit()
        except Exception as desc_exc:
            logger.error("Failed to generate description: %s", desc_exc)

        logger.info(
            "Document %s processed: %d chunks upserted into %s",
            doc_id,
            chunk_index,
            collection_name,
        )

    except Exception as exc:
        logger.error(
            "Failed to process document %s: %s", document_id, exc, exc_info=True
        )
        try:
            document.status = DocumentStatus.failed
            db.commit()
        except Exception:
            db.rollback()
