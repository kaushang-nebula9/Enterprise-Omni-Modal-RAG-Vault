import sys
import os
import tempfile
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.base import Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.query_session import QuerySession
from app.models.query_message import QueryMessage
from app.models.enums import MessageRole
from app.models.generated_report import GeneratedReport
from app.models.report_agent_run import ReportAgentRun
from app.api.reports import create_report, get_report_status, download_report
from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

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
        is_active=True,
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


def test_create_report_empty_session(db):
    user = db.user
    tenant = db.tenant

    # Create empty query session
    query_session = QuerySession(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant.id,
        title="Empty Session",
    )
    db.add(query_session)
    db.commit()

    # Generating report should raise 400
    with pytest.raises(HTTPException) as exc_info:
        create_report(session_id=query_session.id, current_user=user, db=db)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "no content to generate a report from" in exc_info.value.detail


def test_create_report_success(db):
    user = db.user
    tenant = db.tenant

    # Create query session with message
    query_session = QuerySession(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant.id,
        title="Valid Session",
    )
    db.add(query_session)
    db.commit()

    message = QueryMessage(
        id=uuid.uuid4(),
        session_id=query_session.id,
        role=MessageRole.user,
        content="Tell me about sales metrics.",
    )
    db.add(message)
    db.commit()

    # Generating report should succeed
    response = create_report(session_id=query_session.id, current_user=user, db=db)
    assert response.report_id is not None
    assert response.status == "generating"

    # Verify report is created in database
    db_report = (
        db.query(GeneratedReport)
        .filter(GeneratedReport.id == response.report_id)
        .first()
    )
    assert db_report is not None
    assert db_report.tenant_id == tenant.id
    assert db_report.session_id == query_session.id
    assert db_report.generated_by == user.id
    assert db_report.title == "Generating..."
    assert db_report.status == "generating"


def test_create_report_different_tenant(db):
    user = db.user

    # Create session with different tenant_id
    different_tenant_id = uuid.uuid4()
    query_session = QuerySession(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=different_tenant_id,
        title="Foreign Session",
    )
    db.add(query_session)
    db.commit()

    message = QueryMessage(
        id=uuid.uuid4(),
        session_id=query_session.id,
        role=MessageRole.user,
        content="Testing...",
    )
    db.add(message)
    db.commit()

    # Should raise 404
    with pytest.raises(HTTPException) as exc_info:
        create_report(session_id=query_session.id, current_user=user, db=db)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_get_report_status_success(db):
    user = db.user
    tenant = db.tenant

    query_session = QuerySession(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant.id,
        title="Session",
    )
    db.add(query_session)
    db.commit()

    report = GeneratedReport(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        session_id=query_session.id,
        generated_by=user.id,
        title="Sales Q2 Report",
        status="generating",
    )
    db.add(report)
    db.commit()

    # Add agent runs
    run1 = ReportAgentRun(
        id=uuid.uuid4(),
        report_id=report.id,
        step_name="gather",
        status="success",
        duration_ms=100,
        created_at=datetime.now(timezone.utc),
    )
    run2 = ReportAgentRun(
        id=uuid.uuid4(),
        report_id=report.id,
        step_name="cluster",
        status="running",
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([run1, run2])
    db.commit()

    response = get_report_status(report_id=report.id, current_user=user, db=db)
    assert response.report_id == report.id
    assert response.status == "generating"
    assert response.title == "Sales Q2 Report"
    assert len(response.steps) == 2
    assert response.steps[0].step_name == "gather"
    assert response.steps[0].status == "success"
    assert response.steps[0].duration_ms == 100
    assert response.steps[1].step_name == "cluster"
    assert response.steps[1].status == "running"


def test_get_report_status_different_tenant(db):
    user = db.user
    tenant = db.tenant

    query_session = QuerySession(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant.id,
        title="Session",
    )
    db.add(query_session)
    db.commit()

    # Different tenant
    different_tenant_id = uuid.uuid4()
    report = GeneratedReport(
        id=uuid.uuid4(),
        tenant_id=different_tenant_id,
        session_id=query_session.id,
        generated_by=user.id,
        title="Foreign Report",
        status="generating",
    )
    db.add(report)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        get_report_status(report_id=report.id, current_user=user, db=db)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_download_report_validation(db):
    user = db.user
    tenant = db.tenant

    query_session = QuerySession(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant.id,
        title="Session",
    )
    db.add(query_session)
    db.commit()

    # Report is generating (not ready)
    report = GeneratedReport(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        session_id=query_session.id,
        generated_by=user.id,
        title="Pending Report",
        status="generating",
    )
    db.add(report)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        download_report(report_id=report.id, current_user=user, db=db)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "not ready for download" in exc_info.value.detail

    # Report is complete but storage_path is null
    report.status = "complete"
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        download_report(report_id=report.id, current_user=user, db=db)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "Report file not found" in exc_info.value.detail


def test_download_report_success(db):
    user = db.user
    tenant = db.tenant

    query_session = QuerySession(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant.id,
        title="Session",
    )
    db.add(query_session)
    db.commit()

    # Create temporary PDF file to mock report storage
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
        temp_pdf.write(b"%PDF-1.4 mock pdf data")
        temp_pdf_path = temp_pdf.name

    try:
        report = GeneratedReport(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            session_id=query_session.id,
            generated_by=user.id,
            title="Complete Report",
            status="complete",
            storage_path=temp_pdf_path,
        )
        db.add(report)
        db.commit()

        response = download_report(report_id=report.id, current_user=user, db=db)
        assert isinstance(response, FileResponse)
        assert response.path == temp_pdf_path
        assert response.media_type == "application/pdf"
        assert (
            response.headers["content-disposition"]
            == f'attachment; filename="report_{report.id}.pdf"'
        )

    finally:
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
