import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.audit_log import AuditLog
from app.services.audit_log_service import log_audit_event

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
    
    # Create required parent rows for ForeignKey constraints
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug="test-tenant")
    role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="Admin", is_admin=True)
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@test.com",
        full_name="Test Admin",
        hashed_password="hash",
        role_id=role.id,
        is_active=True
    )
    session.add_all([tenant, role, user])
    session.commit()
    
    session.tenant = tenant
    session.user = user
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

def test_log_audit_event(db):
    tenant = db.tenant
    user = db.user
    
    # 1. Log audit event
    log = log_audit_event(
        db=db,
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action="role.created",
        description="Created role 'Manager'",
        metadata={"role_name": "Manager"}
    )
    
    assert log.id is not None
    assert log.tenant_id == tenant.id
    assert log.actor_user_id == user.id
    assert log.action == "role.created"
    assert log.description == "Created role 'Manager'"
    assert log.metadata_ == {"role_name": "Manager"}
    assert log.created_at is not None
    
    # 2. Query from database
    db_log = db.query(AuditLog).filter(AuditLog.id == log.id).first()
    assert db_log is not None
    assert db_log.description == "Created role 'Manager'"
    assert db_log.actor.full_name == "Test Admin"
