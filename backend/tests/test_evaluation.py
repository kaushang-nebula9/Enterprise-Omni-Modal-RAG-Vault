import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.models.tenant import Tenant
from app.models.query_log import QueryLog
from app.models.evaluation import EvaluationRun, EvaluationResult
from app.models.enums import EvaluationStatus
from app.tasks.evaluation_tasks import clean_and_parse_json

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

def test_json_parsing_defensive():
    # 1. Clean JSON response
    res1 = clean_and_parse_json('{"faithfulness_score": 85, "relevance_score": 90, "unsupported_claims": [], "reasoning": "great answer"}')
    assert res1["faithfulness_score"] == 85
    assert res1["relevance_score"] == 90
    assert res1["unsupported_claims"] == []
    assert res1["reasoning"] == "great answer"

    # 2. Markdown fenced JSON response
    res2 = clean_and_parse_json('```json\n{"faithfulness_score": 100, "relevance_score": 50, "unsupported_claims": ["claim1"], "reasoning": "some errors"}\n```')
    assert res2["faithfulness_score"] == 100
    assert res2["relevance_score"] == 50
    assert res2["unsupported_claims"] == ["claim1"]
    assert res2["reasoning"] == "some errors"

def test_evaluation_models(db):
    # Setup tenant and user
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Create run
    run = EvaluationRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        requested_by_user_id=user_id,
        status=EvaluationStatus.pending,
        query_count=5,
        date_range_start=datetime.now(timezone.utc) - timedelta(days=1),
        date_range_end=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()

    # Query run
    db_run = db.query(EvaluationRun).filter(EvaluationRun.id == run.id).first()
    assert db_run is not None
    assert db_run.status == EvaluationStatus.pending
    assert db_run.query_count == 5

    # Log a query
    log = QueryLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        question="What is this database?",
        contexts=["This is a PostgreSQL database in memory."],
        answer="It is a PostgreSQL database.",
        created_at=datetime.now(timezone.utc)
    )
    db.add(log)
    db.commit()

    # Create result
    res = EvaluationResult(
        id=uuid.uuid4(),
        evaluation_run_id=run.id,
        query_log_id=log.id,
        faithfulness_score=100,
        relevance_score=80,
        unsupported_claims=[],
        reasoning="Highly faithful and relevant.",
        created_at=datetime.now(timezone.utc)
    )
    db.add(res)
    db.commit()

    # Fetch and check relations
    db_res = db.query(EvaluationResult).filter(EvaluationResult.id == res.id).first()
    assert db_res is not None
    assert db_res.evaluation_run_id == run.id
    assert db_res.query_log_id == log.id
    assert db_res.query_log.question == "What is this database?"
    assert db_res.evaluation_run.status == EvaluationStatus.pending
