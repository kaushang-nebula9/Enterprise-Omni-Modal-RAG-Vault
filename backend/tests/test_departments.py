import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base
from app.models.role import Role
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.department import Department
from app.models.enums import FileType, DocumentStatus, OwnerType, Visibility

# Use in-memory SQLite database for testing
DATABASE_URL = "sqlite:///:memory:"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


@pytest.fixture(name="db")
def db_fixture():
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_department(db):
    tenant_id = uuid.uuid4()
    dept = Department(id=uuid.uuid4(), tenant_id=tenant_id, name="Engineering")
    db.add(dept)
    db.commit()

    # Check database
    d = db.query(Department).filter(Department.name == "Engineering").first()
    assert d is not None
    assert d.tenant_id == tenant_id


def test_assign_role_to_department(db):
    tenant_id = uuid.uuid4()
    dept = Department(id=uuid.uuid4(), tenant_id=tenant_id, name="Sales")
    db.add(dept)
    db.commit()

    role = Role(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Sales Rep",
        parent_role_id=None,
        department_id=dept.id,
    )
    db.add(role)
    db.commit()

    # Check relation
    r = db.query(Role).filter(Role.name == "Sales Rep").first()
    assert r is not None
    assert r.department_id == dept.id
    assert r.department_name == "Sales"


def test_assign_document_to_department(db):
    tenant_id = uuid.uuid4()

    # Create department
    dept = Department(id=uuid.uuid4(), tenant_id=tenant_id, name="Marketing")
    db.add(dept)

    # Create roles inside department
    role1 = Role(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Marketing Mgr",
        parent_role_id=None,
        department_id=dept.id,
    )
    role2 = Role(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Marketing Assoc",
        parent_role_id=None,
        department_id=dept.id,
    )

    # Create a role outside department
    role3 = Role(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="HR Mgr",
        parent_role_id=None,
        department_id=None,
    )

    db.add_all([role1, role2, role3])
    db.commit()

    # Create document
    doc_id = uuid.uuid4()
    document = Document(
        id=doc_id,
        tenant_id=tenant_id,
        uploaded_by=uuid.uuid4(),
        filename="marketing_brief.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.org_wide,
        chunk_count=0,
        qdrant_collection="test_collection",
        status=DocumentStatus.ready,
        file_path="/path/marketing_brief.pdf",
        file_size=100,
    )
    db.add(document)
    db.commit()

    # Setup pre-existing policy for role1 (to test skip logic)
    policy_pre = DocumentAccessPolicy(
        document_id=doc_id,
        role_id=role1.id,
        granted_via="direct",
        inherited_from_role_id=None,
    )
    db.add(policy_pre)
    db.commit()

    # Perform assignment logic matching documents.py endpoint:
    # 3. Find all roles belonging to this tenant where department_id matches dept.id
    roles = (
        db.query(Role)
        .filter(Role.department_id == dept.id, Role.tenant_id == tenant_id)
        .all()
    )

    # 4. Create DocumentAccessPolicy rows for these roles if they don't already have any policy
    for role in roles:
        existing = (
            db.query(DocumentAccessPolicy)
            .filter(
                DocumentAccessPolicy.document_id == doc_id,
                DocumentAccessPolicy.role_id == role.id,
            )
            .first()
        )
        if not existing:
            policy = DocumentAccessPolicy(
                document_id=doc_id,
                role_id=role.id,
                granted_via="department",
                granted_via_department_id=dept.id,
                inherited_from_role_id=None,
            )
            db.add(policy)
    db.commit()

    # Check access policies
    policies = (
        db.query(DocumentAccessPolicy)
        .filter(DocumentAccessPolicy.document_id == doc_id)
        .all()
    )

    # We should have two policies:
    # 1. role1 (retained as "direct", skip logic worked)
    # 2. role2 (newly added as "department")
    # role3 (not added since not in department)
    assert len(policies) == 2

    policy_map = {p.role_id: p for p in policies}
    assert role1.id in policy_map
    assert policy_map[role1.id].granted_via == "direct"
    assert policy_map[role1.id].granted_via_department_id is None

    assert role2.id in policy_map
    assert policy_map[role2.id].granted_via == "department"
    assert policy_map[role2.id].granted_via_department_id == dept.id

    assert role3.id not in policy_map
