"""
Documents API routes — upload, list, download, delete, and access management.
All routes are admin-only and scoped to the current user's tenant.
"""

import uuid
import logging
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    Query,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.core.dependencies import require_admin, get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.role import Role
from app.services.audit_log_service import log_audit_event
from app.models.enums import DocumentStatus, FileType, OwnerType, Visibility
from app.schemas.document import (
    DocumentResponse,
    DocumentWithAccessResponse,
    UpdateDocumentAccessRequest,
    AssignDepartmentRequest,
)
from app.schemas.auth import RoleResponse
from app.services.storage_service import save_file, delete_file, get_absolute_path
from app.tasks.document_tasks import process_document_task
from app.services.qdrant_service import delete_document_vectors, update_document_payload
from app.services.role_service import get_role_ancestors

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
    ".csv": FileType.csv,
    ".mp3": FileType.audio,
    ".wav": FileType.audio,
    ".m4a": FileType.audio,
}


def _load_document_with_policies(
    db: Session, document_id: uuid.UUID, tenant_id: uuid.UUID
) -> Document:
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return doc


def _create_policies_with_inheritance(
    db: Session,
    document_id: uuid.UUID,
    direct_role_ids: list[uuid.UUID],
    unchecked_ancestor_ids: list[uuid.UUID] | None = None,
) -> None:
    """
    Create DocumentAccessPolicy rows for each direct role, then walk up each
    role's ancestor chain and create inherited rows for every ancestor that
    doesn't already have access to this document, unless they are explicitly
    excluded in unchecked_ancestor_ids.
    """
    from app.services.notification_service import create_notification
    from app.models.enums import NotificationType

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return

    # Track which role_ids already have a policy for this document
    covered: set[uuid.UUID] = set()

    # 1. Create direct policies
    for role_id in direct_role_ids:
        if role_id in covered:
            continue
        policy = DocumentAccessPolicy(
            document_id=document_id,
            role_id=role_id,
            granted_via="direct",
            inherited_from_role_id=None,
        )
        db.add(policy)
        covered.add(role_id)

        # Notify users in direct role
        role_users = db.query(User).filter(User.role_id == role_id).all()
        for user in role_users:
            create_notification(
                db=db,
                user_id=user.id,
                tenant_id=user.tenant_id,
                type=NotificationType.document_access_direct,
                message=f"You have been granted direct access to document: {document.filename}",
                related_document_id=document_id,
                related_role_id=role_id,
                flush_only=True,
            )

    # 2. Create inherited policies for ancestors of each direct role
    unchecked_set = set(unchecked_ancestor_ids or [])
    for role_id in direct_role_ids:
        ancestors = get_role_ancestors(role_id, db)
        child_role = db.query(Role).filter(Role.id == role_id).first()
        child_role_name = child_role.name if child_role else "another role"

        for ancestor in ancestors:
            if ancestor.id in covered:
                continue
            if ancestor.id in unchecked_set:
                continue
            # Check if ancestor already has any access policy for this document
            existing = (
                db.query(DocumentAccessPolicy)
                .filter(
                    DocumentAccessPolicy.document_id == document_id,
                    DocumentAccessPolicy.role_id == ancestor.id,
                )
                .first()
            )
            if existing:
                covered.add(ancestor.id)
                continue

            policy = DocumentAccessPolicy(
                document_id=document_id,
                role_id=ancestor.id,
                granted_via="inherited",
                inherited_from_role_id=role_id,
            )
            db.add(policy)
            covered.add(ancestor.id)

            # Notify users in ancestor role
            ancestor_users = db.query(User).filter(User.role_id == ancestor.id).all()
            for user in ancestor_users:
                create_notification(
                    db=db,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    type=NotificationType.document_access_inherited_hierarchy,
                    message=f"You have been granted inherited access to document: {document.filename} (inherited from role: {child_role_name})",
                    related_document_id=document_id,
                    related_role_id=ancestor.id,
                    flush_only=True,
                )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=DocumentWithAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: UploadFile = File(...),
    role_ids: list[str] = Form(default=[]),
    unchecked_ancestor_ids: list[str] = Form(default=[]),
    department_ids: list[str] = Form(default=[]),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Upload a document, save it to the filesystem, create DB records, and
    run the ingestion pipeline synchronously.
    """
    from app.models.department import Department

    # Validate that at least one role or department is selected
    if not role_ids and not department_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one role or department must be selected",
        )

    # Validate and parse role UUIDs
    parsed_role_ids: list[uuid.UUID] = []
    if role_ids:
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
            role = (
                db.query(Role)
                .filter(
                    Role.id == role_id,
                    Role.tenant_id == current_admin.tenant_id,
                )
                .first()
            )
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid role",
                )

    # Validate and parse unchecked ancestor UUIDs
    parsed_unchecked_ids: list[uuid.UUID] = []
    if unchecked_ancestor_ids:
        for rid in unchecked_ancestor_ids:
            try:
                parsed_unchecked_ids.append(uuid.UUID(rid))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid unchecked ancestor ID format: {rid}",
                )

        # Validate each unchecked ancestor role belongs to tenant
        for rid in parsed_unchecked_ids:
            role = (
                db.query(Role)
                .filter(
                    Role.id == rid,
                    Role.tenant_id == current_admin.tenant_id,
                )
                .first()
            )
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid unchecked ancestor role",
                )

    # Validate and parse department UUIDs
    parsed_dept_ids: list[uuid.UUID] = []
    if department_ids:
        for did in department_ids:
            try:
                parsed_dept_ids.append(uuid.UUID(did))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid department ID format: {did}",
                )

        # Validate each department exists and belongs to this tenant
        for dept_id in parsed_dept_ids:
            dept = (
                db.query(Department)
                .filter(
                    Department.id == dept_id,
                    Department.tenant_id == current_admin.tenant_id,
                )
                .first()
            )
            if not dept:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid department",
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
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection=collection_name,
        status=DocumentStatus.pending,
        file_path=file_path,
        file_size=file.size,
    )
    db.add(document)
    # Flush so the document row exists in the DB before policies and
    # notifications try to reference it via foreign keys.
    db.flush()

    # Create access policy records (direct + inherited for ancestors)
    if parsed_role_ids:
        _create_policies_with_inheritance(
            db, document_id, parsed_role_ids, parsed_unchecked_ids
        )

    # Create department-based access policies
    if parsed_dept_ids:
        from app.services.notification_service import create_notification
        from app.models.enums import NotificationType

        for dept_id in parsed_dept_ids:
            dept_roles = (
                db.query(Role)
                .filter(Role.department_id == dept_id, Role.tenant_id == tenant_id)
                .all()
            )
            for role in dept_roles:
                existing = (
                    db.query(DocumentAccessPolicy)
                    .filter(
                        DocumentAccessPolicy.document_id == document_id,
                        DocumentAccessPolicy.role_id == role.id,
                    )
                    .first()
                )
                if not existing:
                    policy = DocumentAccessPolicy(
                        document_id=document_id,
                        role_id=role.id,
                        granted_via="department",
                        granted_via_department_id=dept_id,
                        inherited_from_role_id=None,
                    )
                    db.add(policy)

            # Notify users whose role belongs to that department
            dept = db.query(Department).filter(Department.id == dept_id).first()
            dept_name = dept.name if dept else "unknown department"
            dept_users = (
                db.query(User).join(Role).filter(Role.department_id == dept_id).all()
            )
            for u in dept_users:
                create_notification(
                    db=db,
                    user_id=u.id,
                    tenant_id=u.tenant_id,
                    type=NotificationType.document_access_inherited_department,
                    message=f"You have been granted access to document: {filename} (via department: {dept_name})",
                    related_document_id=document_id,
                    related_department_id=dept_id,
                    flush_only=True,
                )

    db.commit()

    # Enqueue the ingestion pipeline as a Celery task
    process_document_task.delay(str(document.id))

    # Reload with policies and roles eager-loaded
    doc = _load_document_with_policies(db, document_id, tenant_id)
    return doc


@router.get("", response_model=list[DocumentWithAccessResponse])
def get_documents(
    collection_id: uuid.UUID | None = Query(None),
    uncategorized: bool = Query(False),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return all organisation-owned documents for the admin's tenant."""
    query = (
        db.query(Document)
        .options(
            joinedload(Document.access_policies).joinedload(DocumentAccessPolicy.role),
            joinedload(Document.collection),
        )
        .filter(
            Document.tenant_id == current_admin.tenant_id,
            Document.owner_type == OwnerType.organisation,
        )
    )

    if collection_id is not None:
        query = query.filter(Document.collection_id == collection_id)
    elif uncategorized:
        query = query.filter(Document.collection_id.is_(None))

    docs = query.all()
    return docs


@router.get("/authorized", response_model=list[DocumentResponse])
def get_authorized_documents(
    collection_id: uuid.UUID | None = Query(None),
    uncategorized: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all organisation-owned documents for the user's tenant where the user's
    role is in the document's access policies.  Include granted_via,
    inherited_from_role_name (resolved), and department_name (resolved) for each document.
    """
    from sqlalchemy.orm import aliased
    from app.models.department import Department
    from app.models.collection import Collection

    InheritedRole = aliased(Role)

    query = (
        db.query(
            Document,
            DocumentAccessPolicy.granted_via,
            InheritedRole.name,
            Department.name,
            Collection.name.label("collection_name"),
        )
        .join(DocumentAccessPolicy, Document.id == DocumentAccessPolicy.document_id)
        .outerjoin(
            InheritedRole,
            DocumentAccessPolicy.inherited_from_role_id == InheritedRole.id,
        )
        .outerjoin(
            Department,
            DocumentAccessPolicy.granted_via_department_id == Department.id,
        )
        .outerjoin(
            Collection,
            Document.collection_id == Collection.id,
        )
        .filter(
            Document.tenant_id == current_user.tenant_id,
            Document.owner_type == OwnerType.organisation,
            DocumentAccessPolicy.role_id == current_user.role_id,
        )
    )

    if collection_id is not None:
        query = query.filter(Document.collection_id == collection_id)
    elif uncategorized:
        query = query.filter(Document.collection_id.is_(None))

    rows = query.all()

    results: list[dict] = []
    for doc, granted_via, inherited_role_name, dept_name, coll_name in rows:
        d = DocumentResponse.model_validate(doc)
        d.granted_via = granted_via
        d.inherited_from_role_name = inherited_role_name
        d.department_name = dept_name
        d.collection_name = coll_name
        results.append(d)
    return results


@router.get("/preview-assignment", response_model=list[RoleResponse])
def preview_assignment(
    role_id: uuid.UUID = Query(...),
    document_id: uuid.UUID | None = Query(None),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Dry-run preview: given a role (and optionally a document), return the list
    of ancestor roles that would also gain access via inheritance.

    If document_id is provided, ancestors that already have direct or inherited
    access to that document are excluded.
    """
    # Validate role belongs to tenant
    role = (
        db.query(Role)
        .filter(
            Role.id == role_id,
            Role.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not found in this organisation",
        )

    ancestors = get_role_ancestors(role_id, db)

    if document_id is not None:
        # Filter out ancestors that already have access
        existing_role_ids = {
            p.role_id
            for p in db.query(DocumentAccessPolicy)
            .filter(DocumentAccessPolicy.document_id == document_id)
            .all()
        }
        ancestors = [a for a in ancestors if a.id not in existing_role_ids]

    return ancestors


@router.get("/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Serve a document file as a download response."""
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

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
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Remove vectors from Qdrant if applicable
    if doc.status == DocumentStatus.ready and doc.file_type not in (
        FileType.excel,
        FileType.csv,
    ):
        try:
            delete_document_vectors(doc.qdrant_collection, str(doc.id))
        except Exception as exc:
            logger.warning(
                "Failed to delete Qdrant vectors for document %s: %s", document_id, exc
            )

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
    then update Qdrant payload to reflect the new role_ids (including inherited).
    """
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Validate each role
    for role_id in request.role_ids:
        role = (
            db.query(Role)
            .filter(
                Role.id == role_id,
                Role.tenant_id == current_admin.tenant_id,
            )
            .first()
        )
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role",
            )

    # Validate unchecked ancestor roles
    if request.unchecked_ancestor_ids:
        for rid in request.unchecked_ancestor_ids:
            role = (
                db.query(Role)
                .filter(
                    Role.id == rid,
                    Role.tenant_id == current_admin.tenant_id,
                )
                .first()
            )
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid unchecked ancestor role",
                )

    # Delete existing policies
    db.query(DocumentAccessPolicy).filter(
        DocumentAccessPolicy.document_id == document_id
    ).delete()

    # Create new policies (direct + inherited for ancestors)
    _create_policies_with_inheritance(
        db, document_id, list(request.role_ids), request.unchecked_ancestor_ids
    )

    db.commit()

    # Build the complete list of role_ids for Qdrant (all policies)
    all_policies = (
        db.query(DocumentAccessPolicy)
        .filter(DocumentAccessPolicy.document_id == document_id)
        .all()
    )
    new_role_ids = [str(p.role_id) for p in all_policies]
    uploader_id = str(doc.uploaded_by)
    if uploader_id not in new_role_ids:
        new_role_ids.append(uploader_id)

    # Update Qdrant payload if vectors exist
    if doc.status == DocumentStatus.ready and doc.file_type not in (
        FileType.excel,
        FileType.csv,
    ):
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

    role_names = []
    if request.role_ids:
        roles = db.query(Role).filter(Role.id.in_(request.role_ids)).all()
        role_names = [r.name for r in roles]
    roles_desc = ", ".join(role_names) if role_names else "none"

    log_audit_event(
        db=db,
        tenant_id=current_admin.tenant_id,
        actor_user_id=current_admin.id,
        action="document.assigned_to_role",
        description=f"Assigned document '{doc.filename}' to roles: {roles_desc}",
        metadata={
            "document_id": str(doc.id),
            "filename": doc.filename,
            "role_ids": [str(rid) for rid in request.role_ids],
            "role_names": role_names,
        },
    )

    return updated_doc


@router.post(
    "/{document_id}/assign-department", response_model=DocumentWithAccessResponse
)
def assign_department(
    document_id: uuid.UUID,
    request: AssignDepartmentRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Looks up all roles where department_id matches request.department_id.
    For each role, creates a DocumentAccessPolicy row with granted_via="department"
    and granted_via_department_id set to that department's id.
    Does NOT walk role hierarchy.
    Skips duplicate rows if role already has direct/inherited/department access.
    """
    from app.models.department import Department

    # 1. Fetch document and check tenant ownership
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id, Document.tenant_id == current_admin.tenant_id
        )
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # 2. Fetch department and check tenant ownership
    dept = (
        db.query(Department)
        .filter(
            Department.id == request.department_id,
            Department.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Department not found"
        )

    # 3. Find all roles belonging to this tenant where department_id matches
    roles = (
        db.query(Role)
        .filter(
            Role.department_id == dept.id, Role.tenant_id == current_admin.tenant_id
        )
        .all()
    )

    # 4. Create DocumentAccessPolicy rows for these roles if they don't already have any policy for this document
    for role in roles:
        existing = (
            db.query(DocumentAccessPolicy)
            .filter(
                DocumentAccessPolicy.document_id == document_id,
                DocumentAccessPolicy.role_id == role.id,
            )
            .first()
        )
        if not existing:
            policy = DocumentAccessPolicy(
                document_id=document_id,
                role_id=role.id,
                granted_via="department",
                granted_via_department_id=dept.id,
                inherited_from_role_id=None,
            )
            db.add(policy)

    # Notify users in this department
    from app.services.notification_service import create_notification
    from app.models.enums import NotificationType

    dept_users = db.query(User).join(Role).filter(Role.department_id == dept.id).all()
    for u in dept_users:
        create_notification(
            db=db,
            user_id=u.id,
            tenant_id=u.tenant_id,
            type=NotificationType.document_access_inherited_department,
            message=f"You have been granted access to document: {doc.filename} (via department: {dept.name})",
            related_document_id=document_id,
            related_department_id=dept.id,
            flush_only=True,
        )

    db.commit()

    log_audit_event(
        db=db,
        tenant_id=current_admin.tenant_id,
        actor_user_id=current_admin.id,
        action="document.assigned_to_department",
        description=f"Assigned document '{doc.filename}' to department '{dept.name}'",
        metadata={
            "document_id": str(doc.id),
            "filename": doc.filename,
            "department_id": str(dept.id),
            "department_name": dept.name,
        },
    )

    # 5. Build the complete list of role_ids for Qdrant (all policies)
    all_policies = (
        db.query(DocumentAccessPolicy)
        .filter(DocumentAccessPolicy.document_id == document_id)
        .all()
    )
    new_role_ids = [str(p.role_id) for p in all_policies]
    uploader_id = str(doc.uploaded_by)
    if uploader_id not in new_role_ids:
        new_role_ids.append(uploader_id)

    # Update Qdrant payload if vectors exist
    if doc.status == DocumentStatus.ready and doc.file_type not in (
        FileType.excel,
        FileType.csv,
    ):
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

    # Reload and return
    return _load_document_with_policies(db, document_id, current_admin.tenant_id)
