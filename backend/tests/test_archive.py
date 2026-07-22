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


@pytest.fixture(autouse=True)
def configure_dependency_overrides():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_admin] = override_require_admin
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_admin, None)


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
    tenant_a = Tenant(id=uuid.uuid4(), name="Tenant A", slug="tenant-a")
    db.add(tenant_a)
    db.commit()

    role_admin_a = Role(
        id=uuid.uuid4(), tenant_id=tenant_a.id, name="Admin", is_admin=True
    )
    role_member_a = Role(
        id=uuid.uuid4(), tenant_id=tenant_a.id, name="Member", is_admin=False
    )
    db.add_all([role_admin_a, role_member_a])
    db.commit()

    admin_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="admin_a@test.com",
        full_name="Admin A",
        hashed_password="hash",
        role_id=role_admin_a.id,
        is_active=True,
    )
    # Associate roles on the user model object for consistency with dependency checks
    admin_a.role = role_admin_a

    member_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="member_a@test.com",
        full_name="Member A",
        hashed_password="hash",
        role_id=role_member_a.id,
        is_active=True,
    )
    member_a.role = role_member_a

    db.add_all([admin_a, member_a])
    db.commit()

    # Create collection
    col_a = Collection(
        id=uuid.uuid4(), tenant_id=tenant_a.id, name="Col A", created_by=admin_a.id
    )
    db.add(col_a)
    db.commit()

    # Create documents
    doc_1 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="doc1.txt",
        file_type=FileType.text,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.pending,
        collection_id=col_a.id,
        is_archived=False,
    )
    doc_2 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        uploaded_by=admin_a.id,
        filename="doc2.txt",
        file_type=FileType.text,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        chunk_count=0,
        qdrant_collection="test",
        status=DocumentStatus.pending,
        collection_id=col_a.id,
        is_archived=False,
    )
    db.add_all([doc_1, doc_2])
    db.commit()

    # Add access policies for member
    p1 = DocumentAccessPolicy(
        document_id=doc_1.id, role_id=role_member_a.id, granted_via="direct"
    )
    p2 = DocumentAccessPolicy(
        document_id=doc_2.id, role_id=role_member_a.id, granted_via="direct"
    )
    db.add_all([p1, p2])
    db.commit()

    return tenant_a, admin_a, member_a, doc_1, doc_2, col_a


def test_archive_document_as_admin_success(db, client):
    _, admin_a, _, doc_1, _, _ = setup_test_data(db)
    test_context["current_user"] = admin_a
    test_context["current_admin"] = admin_a

    response = client.patch(f"/api/v1/documents/{doc_1.id}/archive")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["is_archived"] is True

    # Check database status
    db.refresh(doc_1)
    assert doc_1.is_archived is True


def test_archive_document_as_member_forbidden(db, client):
    _, admin_a, member_a, doc_1, _, _ = setup_test_data(db)
    test_context["current_user"] = member_a
    test_context["current_admin"] = None  # require_admin fails

    response = client.patch(f"/api/v1/documents/{doc_1.id}/archive")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_unarchive_document_as_admin_success(db, client):
    _, admin_a, _, doc_1, _, _ = setup_test_data(db)
    doc_1.is_archived = True
    db.commit()

    test_context["current_user"] = admin_a
    test_context["current_admin"] = admin_a

    response = client.patch(f"/api/v1/documents/{doc_1.id}/unarchive")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["is_archived"] is False

    # Check database status
    db.refresh(doc_1)
    assert doc_1.is_archived is False


def test_unarchive_document_as_member_forbidden(db, client):
    _, admin_a, member_a, doc_1, _, _ = setup_test_data(db)
    doc_1.is_archived = True
    db.commit()

    test_context["current_user"] = member_a
    test_context["current_admin"] = None

    response = client.patch(f"/api/v1/documents/{doc_1.id}/unarchive")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_documents_list_filtering(db, client):
    _, admin_a, member_a, doc_1, doc_2, col_a = setup_test_data(db)
    doc_1.is_archived = True
    db.commit()

    # Admin list shows both documents
    test_context["current_user"] = admin_a
    test_context["current_admin"] = admin_a
    response = client.get("/api/v1/documents")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    doc_ids = [d["id"] for d in data]
    assert str(doc_1.id) in doc_ids
    assert str(doc_2.id) in doc_ids

    # Member authorized list only shows doc2 (since doc1 is archived)
    test_context["current_user"] = member_a
    test_context["current_admin"] = None
    response = client.get("/api/v1/documents/authorized")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(doc_2.id)

    # Member collections list has document counts ignoring archived documents
    response = client.get("/api/collections")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_documents"] == 1
    assert data["collections"][0]["document_count"] == 1

    # Admin collections list includes archived documents in count
    test_context["current_user"] = admin_a
    response = client.get("/api/collections")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_documents"] == 2
    assert data["collections"][0]["document_count"] == 2
