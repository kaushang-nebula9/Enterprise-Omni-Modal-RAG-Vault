import sys
import os
import json
import uuid
import pytest
from unittest.mock import patch, MagicMock
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
from app.tasks.report_agent import run_report_generation_agent
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


@patch("app.tasks.report_agent.get_anthropic_client")
@patch("redis.from_url")
def test_run_report_generation_agent_e2e(mock_redis, mock_get_client, db):
    # Setup mocks
    mock_redis_client = MagicMock()
    mock_redis.return_value = mock_redis_client

    user = db.user
    tenant = db.tenant

    # 1. Create a query session with a message pair
    query_session = QuerySession(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant.id,
        title="Session",
    )
    db.add(query_session)
    db.commit()

    user_msg = QueryMessage(
        id=uuid.uuid4(),
        session_id=query_session.id,
        role=MessageRole.user,
        content="How was Q1?",
    )
    assistant_msg = QueryMessage(
        id=uuid.uuid4(),
        session_id=query_session.id,
        role=MessageRole.assistant,
        content="Q1 was great.",
        chart_spec={
            "chart_type": "bar",
            "data": [{"name": "A", "val": 10}],
            "x_key": "name",
            "series": [{"key": "val", "name": "Value", "color": "#000"}],
        },
    )
    db.add_all([user_msg, assistant_msg])
    db.commit()

    # 2. Create GeneratedReport row
    report = GeneratedReport(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        session_id=query_session.id,
        generated_by=user.id,
        title="Generating...",
        status="generating",
    )
    db.add(report)
    db.commit()

    # Mock controller decisions and step outputs
    decisions = [
        # Decision after gather step
        {
            "next_step": "cluster",
            "reasoning": "Clustering time",
            "retry_current": False,
            "retry_reason": None,
            "adjustments": [],
        },
        # Decision after cluster step (first fails index count validation, triggers retry)
        {
            "next_step": "cluster",
            "reasoning": "Failed validation indices",
            "retry_current": True,
            "retry_reason": "Missing indices",
            "adjustments": [],
        },
        # Decision after cluster step (succeeds)
        {
            "next_step": "synthesize",
            "reasoning": "Synthesize time",
            "retry_current": False,
            "retry_reason": None,
            "adjustments": [],
        },
        # Decision after synthesize step
        {
            "next_step": "assemble",
            "reasoning": "Assemble time",
            "retry_current": False,
            "retry_reason": None,
            "adjustments": [],
        },
        # Decision after assemble step
        {
            "next_step": "render",
            "reasoning": "Render time",
            "retry_current": False,
            "retry_reason": None,
            "adjustments": [],
        },
        # Decision after render step
        {
            "next_step": "deliver",
            "reasoning": "Deliver time",
            "retry_current": False,
            "retry_reason": None,
            "adjustments": [],
        },
        # Decision after deliver step
        {
            "next_step": "done",
            "reasoning": "Done",
            "retry_current": False,
            "retry_reason": None,
            "adjustments": [],
        },
    ]

    cluster_attempts = [0]

    def mock_create(*args, **kwargs):
        prompt = kwargs.get("messages")[0]["content"]
        mock_resp = MagicMock()

        if "Group the following question-answer pairs" in prompt:
            cluster_attempts[0] += 1
            if cluster_attempts[0] == 1:
                # Fails validation (empty qa_pair_indices)
                mock_resp.content = [
                    MagicMock(
                        text=json.dumps(
                            {
                                "clusters": [
                                    {
                                        "cluster_id": 1,
                                        "topic_label": "Topic One",
                                        "topic_description": "First topic description",
                                        "qa_pair_indices": [],
                                    }
                                ]
                            }
                        )
                    )
                ]
            else:
                # Valid
                mock_resp.content = [
                    MagicMock(
                        text=json.dumps(
                            {
                                "clusters": [
                                    {
                                        "cluster_id": 1,
                                        "topic_label": "Topic One",
                                        "topic_description": "First topic description",
                                        "qa_pair_indices": [0],
                                    }
                                ]
                            }
                        )
                    )
                ]
        elif "write all sections of a business intelligence report" in prompt:
            mock_resp.content = [
                MagicMock(
                    text=json.dumps(
                        {
                            "title": "BI Report Title",
                            "executive_summary": "Exec summary description.",
                            "key_findings": [
                                "Finding one.",
                                "Finding two.",
                                "Finding three.",
                            ],
                            "detailed_findings": [
                                {
                                    "cluster_id": 1,
                                    "section_title": "Section Title One",
                                    "narrative": "Detailed narrative for topic one.",
                                    "citations": ["doc-name.pdf page 5"],
                                }
                            ],
                        }
                    )
                )
            ]
        else:
            decision = (
                decisions.pop(0)
                if decisions
                else {"next_step": "done", "reasoning": "done"}
            )
            mock_resp.content = [MagicMock(text=json.dumps(decision))]

        return mock_resp

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = mock_create
    mock_get_client.return_value = mock_client

    # 3. Execute Celery task directly
    db.close = MagicMock()
    with patch("app.tasks.report_agent.SessionLocal", return_value=db):
        run_report_generation_agent(str(report.id))

    # 4. Verify Database State
    db.refresh(report)
    assert report.status == "complete"
    assert report.title == "BI Report Title"
    assert report.storage_path is not None
    assert os.path.exists(report.storage_path)

    # Clean up PDF file
    if os.path.exists(report.storage_path):
        os.remove(report.storage_path)

    # 5. Verify Runs log
    runs = db.query(ReportAgentRun).filter(ReportAgentRun.report_id == report.id).all()
    # Runs should include: gather, cluster (attempt 1), cluster (attempt 2), synthesize, assemble, render, deliver
    steps = [run.step_name for run in runs]
    assert "gather" in steps
    assert steps.count("cluster") == 2
    assert "synthesize" in steps
    assert "assemble" in steps
    assert "render" in steps
    assert "deliver" in steps

    # 6. Verify SSE notification publish
    mock_redis_client.publish.assert_called_once()
    channel, payload_str = mock_redis_client.publish.call_args[0]
    assert channel == f"notifications:{user.id}"
    payload = json.loads(payload_str)
    assert payload["type"] == "report_ready"
    assert payload["report_id"] == str(report.id)
    assert payload["title"] == "BI Report Title"
    assert payload["session_id"] == str(query_session.id)
