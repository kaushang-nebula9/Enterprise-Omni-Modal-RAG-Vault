import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType, OwnerType, Visibility
from app.schemas.document import DocumentWithAccessResponse
from app.services.storage_service import save_file, delete_file, get_absolute_path
from app.services.document_processor import process_document
from app.services.qdrant_service import delete_document_vectors

logger = logging.getLogger(__name__)

router = APIRouter()

EXTENSION_TO_FILE_TYPE: dict[str, FileType] = {
    ".pdf": FileType.pdf,
    ".docx": FileType.docx,
    ".txt": FileType.text,
    ".pptx": FileType.pptx,
    ".xlsx": FileType.excel,
    ".xls": FileType.excel,
    ".mp3": FileType.audio,
    ".wav": FileType.audio,
    ".m4a": FileType.audio,
}

@router.post("/upload", response_model=DocumentWithAccessResponse, status_code=status.HTTP_201_CREATED)
def upload_personal_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a personal document for the current user.
    """
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_type = EXTENSION_TO_FILE_TYPE.get(ext)
    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        )

    document_id = uuid.uuid4()
    file_path = save_file(file, str(current_user.tenant_id), str(document_id))

    # Personal documents use a user-specific collection
    collection_name = f"user_{current_user.id}"

    document = Document(
        id=document_id,
        tenant_id=current_user.tenant_id,
        uploaded_by=current_user.id,
        filename=filename,
        file_type=file_type,
        owner_type=OwnerType.private,
        visibility=Visibility.private,
        chunk_count=0,
        qdrant_collection=collection_name,
        status=DocumentStatus.pending,
        file_path=file_path,
        file_size=file.size,
    )
    db.add(document)
    db.commit()

    # Process document
    process_document(str(document_id), db)

    doc = (
        db.query(Document)
        .options(
            joinedload(Document.access_policies)
        )
        .filter(Document.id == document_id)
        .first()
    )
    return doc

@router.get("", response_model=list[DocumentWithAccessResponse])
def get_personal_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all personal documents for the current user."""
    docs = (
        db.query(Document)
        .options(
            joinedload(Document.access_policies)
        )
        .filter(
            Document.tenant_id == current_user.tenant_id,
            Document.uploaded_by == current_user.id,
            Document.owner_type == OwnerType.private,
        )
        .all()
    )
    return docs

@router.get("/{document_id}/download")
def download_personal_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve a personal document file as a download response."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
        Document.uploaded_by == current_user.id,
        Document.owner_type == OwnerType.private,
    ).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    absolute_path = get_absolute_path(doc.file_path)
    return FileResponse(
        path=absolute_path,
        filename=doc.filename,
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )

@router.delete("/{document_id}")
def delete_personal_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a personal document."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id,
        Document.uploaded_by == current_user.id,
        Document.owner_type == OwnerType.private,
    ).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.status == DocumentStatus.ready and doc.file_type != FileType.excel:
        try:
            delete_document_vectors(doc.qdrant_collection, str(doc.id))
        except Exception as exc:
            logger.warning("Failed to delete Qdrant vectors for document %s: %s", document_id, exc)

    if doc.file_path:
        delete_file(doc.file_path)

    db.delete(doc)
    db.commit()

    return {"message": "Personal document deleted successfully"}
