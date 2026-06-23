import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.role import Role
from app.models.document import Document
from app.models.document_access_policy import DocumentAccessPolicy
from app.models.enums import FileType, DocumentStatus, OwnerType, Visibility
from app.services.role_service import get_role_ancestors, check_role_cycle
from app.api.v1.documents import _create_policies_with_inheritance

# Use in-memory SQLite database for testing
DATABASE_URL = "sqlite:///:memory:"

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

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

def test_get_role_ancestors_empty(db):
    tenant_id = uuid.uuid4()
    role = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="CEO", parent_role_id=None)
    db.add(role)
    db.commit()

    ancestors = get_role_ancestors(role.id, db)
    assert len(ancestors) == 0

def test_get_role_ancestors_chain(db):
    tenant_id = uuid.uuid4()
    ceo = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="CEO", parent_role_id=None)
    vp = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="VP", parent_role_id=ceo.id)
    manager = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="Manager", parent_role_id=vp.id)
    dev = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="Developer", parent_role_id=manager.id)
    
    db.add_all([ceo, vp, manager, dev])
    db.commit()

    # Ancestors of Developer should be: Manager -> VP -> CEO
    ancestors = get_role_ancestors(dev.id, db)
    assert len(ancestors) == 3
    assert ancestors[0].id == manager.id
    assert ancestors[1].id == vp.id
    assert ancestors[2].id == ceo.id

def test_get_role_ancestors_cycle_safety(db):
    tenant_id = uuid.uuid4()
    role_a = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="RoleA", parent_role_id=None)
    role_b = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="RoleB", parent_role_id=role_a.id)
    
    db.add_all([role_a, role_b])
    db.commit()

    # Manually force a cycle A -> B -> A for loop safety testing
    role_a.parent_role_id = role_b.id
    db.commit()

    ancestors = get_role_ancestors(role_a.id, db)
    # The safety visited set/MAX_HIERARCHY_DEPTH should prevent infinite loop
    assert len(ancestors) <= 50

def test_check_role_cycle(db):
    tenant_id = uuid.uuid4()
    ceo = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="CEO", parent_role_id=None)
    vp = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="VP", parent_role_id=ceo.id)
    manager = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="Manager", parent_role_id=vp.id)
    
    db.add_all([ceo, vp, manager])
    db.commit()

    # Normal hierarchy has no cycles
    assert not check_role_cycle(ceo.id, None, db)
    assert not check_role_cycle(manager.id, ceo.id, db)

    # Self-reference is a cycle
    assert check_role_cycle(ceo.id, ceo.id, db)

    # Setting CEO's parent to VP would form a cycle (CEO -> VP -> CEO)
    assert check_role_cycle(ceo.id, vp.id, db)

    # Setting CEO's parent to Manager would form a cycle (CEO -> VP -> Manager -> CEO)
    assert check_role_cycle(ceo.id, manager.id, db)

    # Setting VP's parent to Manager would form a cycle (VP -> Manager -> VP)
    assert check_role_cycle(vp.id, manager.id, db)

def test_create_policies_with_inheritance(db):
    tenant_id = uuid.uuid4()
    ceo = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="CEO", parent_role_id=None)
    vp = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="VP", parent_role_id=ceo.id)
    manager = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="Manager", parent_role_id=vp.id)
    dev = Role(id=uuid.uuid4(), tenant_id=tenant_id, name="Developer", parent_role_id=manager.id)
    
    db.add_all([ceo, vp, manager, dev])
    db.commit()

    doc_id = uuid.uuid4()
    document = Document(
        id=doc_id,
        tenant_id=tenant_id,
        uploaded_by=uuid.uuid4(),
        filename="test.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.org_wide,
        chunk_count=0,
        qdrant_collection="test_collection",
        status=DocumentStatus.ready,
        file_path="/path/test.pdf",
        file_size=100
    )
    db.add(document)
    db.commit()

    # Assign directly to Manager
    _create_policies_with_inheritance(db, doc_id, [manager.id])
    db.commit()

    # Policies should exist for Manager (direct), VP (inherited), and CEO (inherited)
    policies = db.query(DocumentAccessPolicy).filter(DocumentAccessPolicy.document_id == doc_id).all()
    assert len(policies) == 3

    policy_map = {p.role_id: p for p in policies}
    
    assert manager.id in policy_map
    assert policy_map[manager.id].granted_via == "direct"
    assert policy_map[manager.id].inherited_from_role_id is None

    assert vp.id in policy_map
    assert policy_map[vp.id].granted_via == "inherited"
    assert policy_map[vp.id].inherited_from_role_id == manager.id

    assert ceo.id in policy_map
    assert policy_map[ceo.id].granted_via == "inherited"
    assert policy_map[ceo.id].inherited_from_role_id == manager.id
