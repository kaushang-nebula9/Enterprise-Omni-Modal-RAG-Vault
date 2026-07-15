import sys
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.document import Document
from app.models.collection import Collection
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.enums import FileType, DocumentStatus, OwnerType, Visibility

DATABASE_URL = "sqlite:///:memory:"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


# Global test state to communicate between fixture and overrides
test_context = {"current_user": None, "current_admin": None, "db_session": None}


def override_get_db():
    yield test_context["db_session"]


def override_get_current_user():
    if not test_context["current_user"]:
        raise Exception("Current user not set in test context")
    return test_context["current_user"]


def override_require_admin():
    if not test_context["current_admin"]:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin role required")
    return test_context["current_admin"]


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[require_admin] = override_require_admin


@pytest.fixture(name="db")
def db_fixture():
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    test_context["db_session"] = session
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        test_context["db_session"] = None
        test_context["current_user"] = None
        test_context["current_admin"] = None


@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)


def setup_test_data(db):
    # 1. Create Tenants
    tenant_a = Tenant(id=uuid.uuid4(), name="Tenant A", slug="tenant-a")
    tenant_b = Tenant(id=uuid.uuid4(), name="Tenant B", slug="tenant-b")
    db.add_all([tenant_a, tenant_b])
    db.commit()

    # 2. Create Roles
    role_admin_a = Role(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Admin")
    role_member_a = Role(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Member")
    role_admin_b = Role(id=uuid.uuid4(), tenant_id=tenant_b.id, name="Admin")
    db.add_all([role_admin_a, role_member_a, role_admin_b])
    db.commit()

    # 3. Create Users
    admin_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="admin_a@test.com",
        full_name="Admin A",
        hashed_password="hash",
        role_id=role_admin_a.id,
        is_active=True,
    )
    member_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="member_a@test.com",
        full_name="Member A",
        hashed_password="hash",
        role_id=role_member_a.id,
        is_active=True,
    )
    admin_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        email="admin_b@test.com",
        full_name="Admin B",
        hashed_password="hash",
        role_id=role_admin_b.id,
        is_active=True,
    )
    db.add_all([admin_a, member_a, admin_b])
    db.commit()

    return tenant_a, tenant_b, admin_a, member_a, admin_b, role_member_a


def test_create_collection_success(db, client):
    tenant_a, _, admin_a, _, _, _ = setup_test_data(db)
    test_context["current_user"] = admin_a
    test_context["current_admin"] = admin_a

    response = client.post(
        "/api/collections",
        json={
            "name": "  Engineering docs  ",
            "description": "Docs related to engineering Team",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Engineering docs"  # Verify stripped name
    assert data["description"] == "Docs related to engineering Team"
    assert data["document_count"] == 0
    assert data["created_by"] == str(admin_a.id)

    # Verify uniqueness in DB
    db_collection = (
        db.query(Collection).filter(Collection.name == "Engineering docs").first()
    )
    assert db_collection is not None
    assert db_collection.tenant_id == tenant_a.id


def test_create_collection_duplicate_name(db, client):
    _, _, admin_a, _, _, _ = setup_test_data(db)
    test_context["current_user"] = admin_a
    test_context["current_admin"] = admin_a

    # Create first
    client.post(
        "/api/collections", json={"name": "Engineering", "description": "first"}
    )

    # Create second with same name
    response = client.post(
        "/api/collections", json={"name": "Engineering", "description": "second"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"]


def test_create_collection_validation(db, client):
    _, _, admin_a, _, _, _ = setup_test_data(db)
    test_context["current_user"] = admin_a
    test_context["current_admin"] = admin_a

    # Empty name
    response = client.post(
        "/api/collections", json={"name": "   ", "description": "empty"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Name too long
    response = client.post(
        "/api/collections", json={"name": "a" * 101, "description": "long"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_admin_only_endpoints(db, client):
    _, _, _, member_a, _, _ = setup_test_data(db)
    test_context["current_user"] = member_a
    # current_admin stays None, so require_admin will raise HTTP 403

    response = client.post("/api/collections", json={"name": "Finance"})
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_list_collections(db, client):
    tenant_a, _, admin_a, member_a, _, role_member_a = setup_test_data(db)

    # 1. Create collections
    col1 = Collection(
        id=uuid.uuid4(), tenant_id=tenant_a.id, name="Marketing", created_by=admin_a.id
    )
    col2 = Collection(
        id=uuid.uuid4(), tenant_id=tenant_a.id, name="Sales", created_by=admin_a.id
    )
    db.add_all([col1, col2])
    db.commit()

    # 2. Create documents and set up access policy for member_a
    doc1 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="marketing1.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.ready,
        collection_id=col1.id,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="uncategorized.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.ready,
        collection_id=None,
    )
    db.add_all([doc1, doc2])
    db.commit()

    # Check list collections endpoint as member
    test_context["current_user"] = member_a
    response = client.get("/api/collections")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["uncategorized_count"] == 1
    assert data["total_documents"] == 2
    assert len(data["collections"]) == 2

    col_map = {c["name"]: c for c in data["collections"]}
    assert col_map["Marketing"]["document_count"] == 1
    assert col_map["Sales"]["document_count"] == 0


def test_rename_collection(db, client):
    tenant_a, _, admin_a, _, _, _ = setup_test_data(db)
    col = Collection(
        id=uuid.uuid4(), tenant_id=tenant_a.id, name="Old Name", created_by=admin_a.id
    )
    db.add(col)
    db.commit()

    test_context["current_user"] = admin_a
    test_context["current_admin"] = admin_a

    response = client.patch(f"/api/collections/{col.id}", json={"name": "  New Name  "})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "New Name"

    # Check DB
    db.refresh(col)
    assert col.name == "New Name"


def test_delete_collection(db, client):
    tenant_a, _, admin_a, _, _, _ = setup_test_data(db)
    col = Collection(
        id=uuid.uuid4(), tenant_id=tenant_a.id, name="Temp", created_by=admin_a.id
    )
    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="doc.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.ready,
        collection_id=col.id,
    )
    db.add_all([col, doc])
    db.commit()

    test_context["current_user"] = admin_a
    test_context["current_admin"] = admin_a

    response = client.delete(f"/api/collections/{col.id}")
    assert response.status_code == status.HTTP_200_OK
    assert "deleted" in response.json()["message"]

    # Check collection is deleted
    assert db.query(Collection).filter(Collection.id == col.id).first() is None
    # Check document is uncategorized (ON DELETE SET NULL)
    db.refresh(doc)
    assert doc.collection_id is None


def test_move_document_to_collection(db, client):
    tenant_a, _, admin_a, _, _, _ = setup_test_data(db)
    col = Collection(
        id=uuid.uuid4(), tenant_id=tenant_a.id, name="Folder", created_by=admin_a.id
    )
    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="doc.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.ready,
        collection_id=None,
    )
    db.add_all([col, doc])
    db.commit()

    test_context["current_user"] = admin_a
    test_context["current_admin"] = admin_a

    # Move to collection
    response = client.patch(
        f"/api/documents/{doc.id}/collection", json={"collection_id": str(col.id)}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["collection_id"] == str(col.id)

    # Remove from collection (uncategorize)
    response = client.patch(
        f"/api/documents/{doc.id}/collection", json={"collection_id": None}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["collection_id"] is None


def test_tenant_isolation(db, client):
    tenant_a, tenant_b, admin_a, _, admin_b, _ = setup_test_data(db)

    # Collection on Tenant A
    col_a = Collection(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="TenantA Folder",
        created_by=admin_a.id,
    )
    db.add(col_a)
    db.commit()

    # User from Tenant B tries to rename Tenant A's collection
    test_context["current_user"] = admin_b
    test_context["current_admin"] = admin_b

    response = client.patch(f"/api/collections/{col_a.id}", json={"name": "Hacked"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_documents_in_collection_rbac(db, client):
    tenant_a, _, admin_a, member_a, _, role_member_a = setup_test_data(db)
    col = Collection(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Protected Folder",
        created_by=admin_a.id,
    )
    db.add(col)
    db.commit()

    # Two documents in this collection
    doc1 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="has_access.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.ready,
        collection_id=col.id,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="no_access.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.ready,
        collection_id=col.id,
    )
    db.add_all([doc1, doc2])
    db.commit()

    # Access policy only for doc1
    policy = DocumentAccessPolicy(
        document_id=doc1.id, role_id=role_member_a.id, granted_via="direct"
    )
    db.add(policy)
    db.commit()

    # Get documents in collection as member_a
    test_context["current_user"] = member_a
    response = client.get(f"/api/collections/{col.id}/documents")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Should only return doc1 due to access policy filtering
    assert len(data) == 1
    assert data[0]["id"] == str(doc1.id)
    assert data[0]["collection_name"] == "Protected Folder"


def test_extend_documents_endpoints_query_params(db, client):
    tenant_a, _, admin_a, member_a, _, role_member_a = setup_test_data(db)
    col = Collection(
        id=uuid.uuid4(), tenant_id=tenant_a.id, name="Reports", created_by=admin_a.id
    )
    db.add(col)
    db.commit()

    doc_in_col = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="in_col.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.ready,
        collection_id=col.id,
    )
    doc_uncat = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="uncat.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.ready,
        collection_id=None,
    )
    db.add_all([doc_in_col, doc_uncat])
    db.commit()

    # Grant access to both
    p1 = DocumentAccessPolicy(
        document_id=doc_in_col.id, role_id=role_member_a.id, granted_via="direct"
    )
    p2 = DocumentAccessPolicy(
        document_id=doc_uncat.id, role_id=role_member_a.id, granted_via="direct"
    )
    db.add_all([p1, p2])
    db.commit()

    test_context["current_user"] = member_a

    # 1. Filter by collection_id
    response = client.get(
        "/api/v1/documents/authorized", params={"collection_id": str(col.id)}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(doc_in_col.id)
    assert data[0]["collection_name"] == "Reports"

    # 2. Filter by uncategorized
    response = client.get(
        "/api/v1/documents/authorized", params={"uncategorized": True}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(doc_uncat.id)
    assert data[0]["collection_name"] is None

    # 3. No filters (both)
    response = client.get("/api/v1/documents/authorized")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
