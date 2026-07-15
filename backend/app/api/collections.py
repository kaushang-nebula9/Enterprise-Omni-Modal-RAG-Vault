import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.core.dependencies import require_admin, get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.collection import Collection
from app.models.enums import OwnerType
from app.schemas.collection import (
    CollectionCreate,
    CollectionRename,
    DocumentMoveToCollection,
    CollectionResponse,
    CollectionListResponse,
)
from app.schemas.document import DocumentResponse, DocumentWithAccessResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/collections", response_model=CollectionListResponse)
def list_collections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all collections for the current tenant with their document counts.
    """
    collections_data = (
        db.query(Collection, func.count(Document.id).label("document_count"))
        .outerjoin(
            Document,
            (Document.collection_id == Collection.id)
            & (Document.owner_type == OwnerType.organisation),
        )
        .filter(Collection.tenant_id == current_user.tenant_id)
        .group_by(Collection.id)
        .all()
    )

    collections_list = []
    for collection, doc_count in collections_data:
        resp = CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            created_by=collection.created_by,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
            document_count=doc_count,
        )
        collections_list.append(resp)

    uncategorized_count = (
        db.query(func.count(Document.id))
        .filter(
            Document.tenant_id == current_user.tenant_id,
            Document.owner_type == OwnerType.organisation,
            Document.collection_id.is_(None),
        )
        .scalar()
    ) or 0

    total_documents = (
        sum(c.document_count for c in collections_list) + uncategorized_count
    )

    return CollectionListResponse(
        collections=collections_list,
        uncategorized_count=uncategorized_count,
        total_documents=total_documents,
    )


@router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_collection(
    payload: CollectionCreate,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new collection. Admin only.
    """
    name_stripped = payload.name.strip()
    existing = (
        db.query(Collection)
        .filter(
            Collection.tenant_id == current_admin.tenant_id,
            Collection.name == name_stripped,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A collection with name '{name_stripped}' already exists.",
        )

    new_collection = Collection(
        tenant_id=current_admin.tenant_id,
        name=name_stripped,
        description=payload.description,
        created_by=current_admin.id,
    )
    db.add(new_collection)
    db.commit()
    db.refresh(new_collection)

    return CollectionResponse(
        id=new_collection.id,
        name=new_collection.name,
        description=new_collection.description,
        created_by=new_collection.created_by,
        created_at=new_collection.created_at,
        updated_at=new_collection.updated_at,
        document_count=0,
    )


@router.patch("/collections/{collection_id}", response_model=CollectionResponse)
def rename_collection(
    collection_id: uuid.UUID,
    payload: CollectionRename,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Rename a collection. Admin only.
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

    name_stripped = payload.name.strip()
    existing = (
        db.query(Collection)
        .filter(
            Collection.tenant_id == current_admin.tenant_id,
            Collection.name == name_stripped,
            Collection.id != collection_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A collection with name '{name_stripped}' already exists.",
        )

    collection.name = name_stripped
    collection.updated_at = func.now()
    db.commit()
    db.refresh(collection)

    doc_count = (
        db.query(func.count(Document.id))
        .filter(
            Document.collection_id == collection.id,
            Document.owner_type == OwnerType.organisation,
        )
        .scalar()
    ) or 0

    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_by=collection.created_by,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        document_count=doc_count,
    )


@router.delete("/collections/{collection_id}")
def delete_collection(
    collection_id: uuid.UUID,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a collection. Admin only.
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.tenant_id == current_admin.tenant_id,
        )
        .first()
    )
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

    db.delete(collection)
    db.commit()

    return {
        "message": "Collection deleted. Documents have been moved to uncategorized."
    }


@router.patch(
    "/documents/{document_id}/collection", response_model=DocumentWithAccessResponse
)
def move_document_to_collection(
    document_id: uuid.UUID,
    payload: DocumentMoveToCollection,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Move a document to a collection, or remove it from its current collection. Admin only.
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id, Document.tenant_id == current_admin.tenant_id
        )
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    if payload.collection_id is not None:
        collection = (
            db.query(Collection)
            .filter(
                Collection.id == payload.collection_id,
                Collection.tenant_id == current_admin.tenant_id,
            )
            .first()
        )
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Collection not found"
            )
        document.collection_id = payload.collection_id
    else:
        document.collection_id = None

    document.updated_at = func.now()
    db.commit()

    from sqlalchemy.orm import joinedload
    from app.models.document_access_policy import DocumentAccessPolicy

    doc = (
        db.query(Document)
        .options(
            joinedload(Document.access_policies).joinedload(DocumentAccessPolicy.role),
            joinedload(Document.collection),
        )
        .filter(Document.id == document_id)
        .first()
    )
    return doc


@router.get(
    "/collections/{collection_id}/documents", response_model=list[DocumentResponse]
)
def get_documents_in_collection(
    collection_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all documents inside a specific collection. Available to all authenticated users.
    """
    collection = (
        db.query(Collection)
        .filter(
            Collection.id == collection_id,
            Collection.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found."
        )

    from sqlalchemy.orm import aliased
    from app.models.role import Role
    from app.models.department import Department
    from app.models.document_access_policy import DocumentAccessPolicy

    InheritedRole = aliased(Role)

    rows = (
        db.query(
            Document,
            DocumentAccessPolicy.granted_via,
            InheritedRole.name,
            Department.name,
            Collection.name,
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
            Document.collection_id == collection_id,
        )
        .all()
    )

    results = []
    for doc, granted_via, inherited_role_name, dept_name, coll_name in rows:
        d = DocumentResponse.model_validate(doc)
        d.granted_via = granted_via
        d.inherited_from_role_name = inherited_role_name
        d.department_name = dept_name
        d.collection_name = coll_name
        results.append(d)

    return results
