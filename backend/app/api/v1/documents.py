"""
Documents API routes — upload, list, download, delete, and access management.
All routes are admin-only and scoped to the current user's tenant.
"""
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.core.dependencies import require_admin, get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.role import Role
from app.models.enums import DocumentStatus, FileType, OwnerType, Visibility
from app.schemas.document import (
    DocumentResponse,
    DocumentWithAccessResponse,
    UpdateDocumentAccessRequest,
)
from app.services.storage_service import save_file, delete_file, get_absolute_path
from app.services.document_processor import process_document, process_document_bg
from app.services.qdrant_service import delete_document_vectors, update_document_payload

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _load_document_with_policies(db: Session, document_id: uuid.UUID, tenant_id: uuid.UUID) -> Document:
    """Fetch a document with its access_policies and nested roles, verifying tenant ownership."""
    doc = (
        db.query(Document)
        .options(
            joinedload(Document.access_policies).joinedload(DocumentAccessPolicy.role)
        )
        .filter(Document.id == document_id, Document.tenant_id == tenant_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=DocumentWithAccessResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    role_ids: list[str] = Form(...),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Upload a document, save it to the filesystem, create DB records, and
    run the ingestion pipeline synchronously.
    """
    # Validate role_ids not empty
    if not role_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one role must be selected",
        )

    # Validate and parse role UUIDs
    parsed_role_ids: list[uuid.UUID] = []
    for rid in role_ids:
        try:
            parsed_role_ids.append(uuid.UUID(rid))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role ID format: {rid}",
            )

    # Validate each role exists and belongs to this tenant
    for role_id in parsed_role_ids:
        role = db.query(Role).filter(
            Role.id == role_id,
            Role.tenant_id == current_admin.tenant_id,
        ).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role",
            )

    # Determine file type from extension
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_type = EXTENSION_TO_FILE_TYPE.get(ext)
    if not file_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        )

    # Generate document ID and save file
    document_id = uuid.uuid4()
    file_path = save_file(file, str(current_admin.tenant_id), str(document_id))

    tenant_id = current_admin.tenant_id
    collection_name = f"tenant_{tenant_id}"

    # Create document record
    document = Document(
        id=document_id,
        tenant_id=tenant_id,
        uploaded_by=current_admin.id,
        filename=filename,
        file_type=file_type,
        owner_type=OwnerType.organisation,
        visibility=Visibility.org_wide,
        chunk_count=0,
        qdrant_collection=collection_name,
        status=DocumentStatus.pending,
        file_path=file_path,
        file_size=file.size,
    )
    db.add(document)

    # Create access policy records
    for role_id in parsed_role_ids:
        policy = DocumentAccessPolicy(
            document_id=document_id,
            role_id=role_id,
        )
        db.add(policy)

    db.commit()

    # Run the ingestion pipeline in the background
    background_tasks.add_task(process_document_bg, str(document_id))

    # Reload with policies and roles eager-loaded
    doc = _load_document_with_policies(db, document_id, tenant_id)
    return doc


@router.get("", response_model=list[DocumentWithAccessResponse])
def get_documents(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return all organisation-owned documents for the admin's tenant."""
    docs = (
        db.query(Document)
        .options(
            joinedload(Document.access_policies).joinedload(DocumentAccessPolicy.role)
        )
        .filter(
            Document.tenant_id == current_admin.tenant_id,
            Document.owner_type == OwnerType.organisation,
        )
        .all()
    )
    return docs


@router.get("/authorized", response_model=list[DocumentResponse])
def get_authorized_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all organisation-owned documents for the user's tenant where the user's
    role is in the document's access policies.
    """
    docs = (
        db.query(Document)
        .join(DocumentAccessPolicy, Document.id == DocumentAccessPolicy.document_id)
        .filter(
            Document.tenant_id == current_user.tenant_id,
            Document.owner_type == OwnerType.organisation,
            DocumentAccessPolicy.role_id == current_user.role_id,
        )
        .all()
    )
    return docs


@router.get("/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Serve a document file as a download response."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.tenant_id == current_admin.tenant_id,
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
def delete_document(
    document_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a document: remove vectors from Qdrant (if ready + not excel),
    delete the file from disk, and remove the DB record.
    """
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.tenant_id == current_admin.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Remove vectors from Qdrant if applicable
    if doc.status == DocumentStatus.ready and doc.file_type != FileType.excel:
        try:
            delete_document_vectors(doc.qdrant_collection, str(doc.id))
        except Exception as exc:
            logger.warning("Failed to delete Qdrant vectors for document %s: %s", document_id, exc)

    # Remove from filesystem
    if doc.file_path:
        delete_file(doc.file_path)

    # Remove from database (cascade handles policies + citations)
    db.delete(doc)
    db.commit()

    return {"message": "Document deleted successfully"}


@router.patch("/{document_id}/access", response_model=DocumentWithAccessResponse)
def update_document_access(
    document_id: uuid.UUID,
    request: UpdateDocumentAccessRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Replace all access policies for a document with the provided role_ids,
    then update Qdrant payload to reflect the new role_ids.
    """
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.tenant_id == current_admin.tenant_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Validate each role
    new_role_ids = [str(rid) for rid in request.role_ids]
    uploader_id = str(doc.uploaded_by)
    if uploader_id not in new_role_ids:
        new_role_ids.append(uploader_id)

    for role_id in request.role_ids:
        role = db.query(Role).filter(
            Role.id == role_id,
            Role.tenant_id == current_admin.tenant_id,
        ).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role",
            )

    # Delete existing policies
    db.query(DocumentAccessPolicy).filter(
        DocumentAccessPolicy.document_id == document_id
    ).delete()

    # Create new policies
    for role_id in request.role_ids:
        policy = DocumentAccessPolicy(
            document_id=document_id,
            role_id=role_id,
        )
        db.add(policy)

    db.commit()

    # Update Qdrant payload if vectors exist
    if doc.status == DocumentStatus.ready and doc.file_type != FileType.excel:
        try:
            update_document_payload(
                doc.qdrant_collection,
                str(doc.id),
                {"role_ids": new_role_ids},
            )
        except Exception as exc:
            logger.warning(
                "Failed to update Qdrant payload for document %s: %s", document_id, exc
            )

    # Reload with updated policies
    updated_doc = _load_document_with_policies(db, document_id, current_admin.tenant_id)
    return updated_doc
