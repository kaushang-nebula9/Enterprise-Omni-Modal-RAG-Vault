import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.document import Document
from app.models.role import Role
from app.models.department import Department
from app.models.available_model import AvailableModel
from app.models.usage_log import UsageLog

from app.services.rag_service import run_rag_pipeline
from app.api.v1.admin import get_usage_summary


from app.api.v1.admin import get_dashboard_overview, get_document_insights
from app.models.enums import FileType, DocumentStatus, OwnerType, Visibility

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

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


class MockEvent:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class MockUsage:
    def __init__(self, input_tokens=10, output_tokens=20):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class MockFinalMessage:
    def __init__(self, input_tokens=10, output_tokens=20):
        self.usage = MockUsage(input_tokens, output_tokens)


class MockStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aiter__(self):
        yield MockEvent("Mocked answer token")

    async def get_final_message(self):
        return MockFinalMessage()


class MockMessages:
    def stream(self, *args, **kwargs):
        return MockStream()


class MockAnthropicClient:
    def __init__(self):
        self.messages = MockMessages()


class MockCrossEncoder:
    def predict(self, pairs):
        return [0.9] * len(pairs)


@pytest.mark.asyncio
async def test_run_rag_pipeline_anthropic_success(db):
    # Set up database entities
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug="test-tenant")
    db.add(tenant)
    db.commit()

    role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="Member", is_default=True)
    db.add(role)
    db.commit()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        role_id=role.id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="password",
        is_active=True,
    )
    db.add(user)
    db.commit()

    def mock_embed_text(text):
        return [0.1] * 1024

    def mock_search_vectors(*args, **kwargs):
        return []

    mock_client = MockAnthropicClient()

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch(
            "app.services.rag_service._get_cross_encoder",
            return_value=MockCrossEncoder(),
        ),
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for event in run_rag_pipeline("test", user, db):
            events.append(event)

        # Verify db insert
        logs = db.query(UsageLog).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.tenant_id == tenant.id
        assert log.user_id == user.id
        assert log.provider == "anthropic"
        assert log.input_tokens == 10
        assert log.output_tokens == 20


@pytest.mark.asyncio
async def test_run_rag_pipeline_openrouter_success(db):
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug="test-tenant")
    db.add(tenant)
    db.commit()

    role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="Member", is_default=True)
    db.add(role)
    db.commit()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        role_id=role.id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="password",
        is_active=True,
    )
    db.add(user)
    db.commit()

    # Mock AvailableModel querying in run_rag_pipeline to resolve openrouter provider

    model_id = uuid.uuid4()
    db_model = AvailableModel(
        id=model_id,
        display_name="OpenRouter Model",
        provider_id="openrouter",
        model_name="meta-llama/llama-3",
        is_active=True,
    )
    db.add(db_model)
    db.commit()

    def mock_embed_text(text):
        return [0.1] * 1024

    def mock_search_vectors(*args, **kwargs):
        return []

    async def mock_stream_openrouter_completion(*args, **kwargs):
        yield "text", "Token 1"
        yield "usage", {"prompt_tokens": 15, "completion_tokens": 25}

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch(
            "app.services.rag_service._get_cross_encoder",
            return_value=MockCrossEncoder(),
        ),
        patch(
            "app.services.openrouter_service.stream_openrouter_completion",
            side_effect=mock_stream_openrouter_completion,
        ),
    ):
        events = []
        async for event in run_rag_pipeline("test", user, db, model_id=model_id):
            events.append(event)

        logs = db.query(UsageLog).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.tenant_id == tenant.id
        assert log.user_id == user.id
        assert log.provider == "openrouter"
        assert log.input_tokens == 15
        assert log.output_tokens == 25


@pytest.mark.asyncio
async def test_run_rag_pipeline_failed_no_log(db):
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug="test-tenant")
    db.add(tenant)
    db.commit()

    role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="Member", is_default=True)
    db.add(role)
    db.commit()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        role_id=role.id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="password",
        is_active=True,
    )
    db.add(user)
    db.commit()

    def mock_embed_text(text):
        return [0.1] * 1024

    def mock_search_vectors(*args, **kwargs):
        return []

    mock_client = MockAnthropicClient()
    mock_client.messages.stream = MagicMock(
        side_effect=Exception("Anthropic API Error")
    )

    with (
        patch("app.services.embedding_service.embed_text", side_effect=mock_embed_text),
        patch(
            "app.services.rag_service.search_vectors", side_effect=mock_search_vectors
        ),
        patch(
            "app.services.rag_service._get_cross_encoder",
            return_value=MockCrossEncoder(),
        ),
        patch(
            "app.services.rag_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for event in run_rag_pipeline("test", user, db):
            events.append(event)

        # Verify db insert was not called
        logs = db.query(UsageLog).all()
        assert len(logs) == 0


def test_get_usage_summary_endpoint(db):
    tenant_id = uuid.uuid4()
    admin_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.com",
        full_name="Admin User",
        hashed_password="hash",
        role_id=uuid.uuid4(),
        is_active=True,
    )
    db.add(admin_user)

    today = datetime.now()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    log1 = UsageLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=admin_user.id,
        provider="anthropic",
        model_string="claude-haiku",
        input_tokens=100,
        output_tokens=200,
        created_at=today,
    )
    log2 = UsageLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=admin_user.id,
        provider="openrouter",
        model_string="llama-3",
        input_tokens=50,
        output_tokens=150,
        created_at=yesterday,
    )
    log3 = UsageLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=admin_user.id,
        provider="anthropic",
        model_string="claude-opus",
        input_tokens=300,
        output_tokens=400,
        created_at=two_days_ago,
    )
    other_tenant_log = UsageLog(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        provider="anthropic",
        model_string="claude-haiku",
        input_tokens=1000,
        output_tokens=2000,
        created_at=today,
    )
    db.add_all([log1, log2, log3, other_tenant_log])
    db.commit()

    resp = get_usage_summary(current_admin=admin_user, db=db)

    assert len(resp.usage) == 3

    # 2 days ago: log3 (anthropic, input 300, output 400)
    assert resp.usage[0].date == two_days_ago.date()
    assert resp.usage[0].request_count == 1
    assert resp.usage[0].total_tokens == 700
    assert resp.usage[0].claude_input_tokens == 300
    assert resp.usage[0].claude_output_tokens == 400
    assert resp.usage[0].openrouter_input_tokens == 0
    assert resp.usage[0].openrouter_output_tokens == 0

    # Yesterday: log2 (openrouter, input 50, output 150)
    assert resp.usage[1].date == yesterday.date()
    assert resp.usage[1].request_count == 1
    assert resp.usage[1].total_tokens == 200
    assert resp.usage[1].claude_input_tokens == 0
    assert resp.usage[1].claude_output_tokens == 0
    assert resp.usage[1].openrouter_input_tokens == 50
    assert resp.usage[1].openrouter_output_tokens == 150

    # Today: log1 (anthropic, input 100, output 200)
    assert resp.usage[2].date == today.date()
    assert resp.usage[2].request_count == 1
    assert resp.usage[2].total_tokens == 300
    assert resp.usage[2].claude_input_tokens == 100
    assert resp.usage[2].claude_output_tokens == 200
    assert resp.usage[2].openrouter_input_tokens == 0
    assert resp.usage[2].openrouter_output_tokens == 0

    resp_anthropic = get_usage_summary(
        provider="anthropic", current_admin=admin_user, db=db
    )
    assert len(resp_anthropic.usage) == 2
    assert all(item.total_tokens in [700, 300] for item in resp_anthropic.usage)

    resp_range = get_usage_summary(
        start_date=yesterday.date(),
        end_date=today.date(),
        current_admin=admin_user,
        db=db,
    )
    assert len(resp_range.usage) == 2
    assert resp_range.usage[0].date == yesterday.date()
    assert resp_range.usage[1].date == today.date()


def test_new_dashboard_endpoints(db):
    tenant = Tenant(id=uuid.uuid4(), name="Stats Org", slug="stats-org")
    db.add(tenant)
    db.commit()

    role = Role(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Admin",
        is_admin=True,
        is_default=True,
    )
    db.add(role)
    db.commit()

    admin_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="stats-admin@example.com",
        full_name="Stats Admin",
        hashed_password="hash",
        role_id=role.id,
        is_active=True,
    )
    db.add(admin_user)
    db.commit()

    department = Department(id=uuid.uuid4(), tenant_id=tenant.id, name="Engineering")
    db.add(department)

    doc1 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        uploaded_by=admin_user.id,
        filename="notes.txt",
        file_type=FileType.text,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        status=DocumentStatus.ready,
        qdrant_collection="test",
        uploaded_at=datetime.now() - timedelta(minutes=5),
    )
    doc2 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        uploaded_by=admin_user.id,
        filename="report.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.organisation,
        visibility=Visibility.public,
        status=DocumentStatus.pending,
        qdrant_collection="test",
        uploaded_at=datetime.now(),
    )
    db.add_all([doc1, doc2])
    db.commit()

    # Test /dashboard-overview endpoint
    overview_resp = get_dashboard_overview(current_admin=admin_user, db=db)
    assert overview_resp.department_count == 1
    assert overview_resp.document_count == 2
    assert overview_resp.role_count == 1  # only default Admin role
    assert overview_resp.member_count == 1

    # Test /document-insights endpoint
    insights_resp = get_document_insights(current_admin=admin_user, db=db)
    assert len(insights_resp.distribution) == 2

    dist_map = {item.file_type: item.count for item in insights_resp.distribution}
    assert dist_map.get("text") == 1
    assert dist_map.get("pdf") == 1

    assert len(insights_resp.recent_documents) == 2
    assert insights_resp.recent_documents[0].filename == "report.pdf"  # Uploaded last
    assert insights_resp.recent_documents[0].uploaded_by == "Stats Admin"
    assert insights_resp.recent_documents[0].status == "pending"
