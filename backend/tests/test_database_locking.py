import sys
import os
import uuid
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.models.role import Role
from app.models.user import User
from app.models.tenant import Tenant
from app.models.query_session import QuerySession
from app.models.external_database import ExternalDatabaseConnection
from app.schemas.chat import QueryRequest
from app.api.v1.chat import send_query

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

    # Create default role, tenant, user
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug="test-tenant")
    session.add(tenant)

    role = Role(id=uuid.uuid4(), name="member", is_admin=False, tenant_id=tenant.id)
    session.add(role)
    session.commit()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="hash",
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    session.commit()

    try:
        yield (session, user, tenant)
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
@patch("app.api.v1.chat.run_rag_pipeline")
@patch(
    "app.services.rate_limit_service.check_and_increment_rate_limit", return_value=True
)
async def test_database_locking_flow(mock_rate_limit, mock_run_rag, db):
    session, user, tenant = db

    # 1. Create a query session
    query_session = QuerySession(user_id=user.id, tenant_id=tenant.id, title="New Chat")
    session.add(query_session)

    # Create external database connection
    db_conn = ExternalDatabaseConnection(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Test DB",
        engine="postgresql",
        host="localhost",
        port=5432,
        database_name="test_db",
        username="postgres",
        password="pwd",
        status="active",
    )
    session.add(db_conn)
    session.commit()

    assert query_session.db_connection_id is None

    # Setup RAG pipeline mock
    async def mock_generator(*args, **kwargs):
        yield {"type": "token", "content": "Analyzing..."}
        yield {
            "type": "done",
            "answer": "Here is your SQL result.",
            "citations": [],
            "model_string": "test-model",
            "generated_sql": "SELECT * FROM test_table;",
            "query_results": [{"col": "val"}],
        }

    mock_run_rag.side_effect = mock_generator

    # 2. Run first query targeting the database connection
    body = QueryRequest(content="Show all data", database_id=db_conn.id)

    response = await send_query(
        session_id=query_session.id, body=body, current_user=user, db=session
    )

    # Consume generator to complete execution
    async for chunk in response.body_iterator:
        pass

    session.refresh(query_session)
    # The session should now be locked to the database connection
    assert query_session.db_connection_id == db_conn.id

    # 3. Verify server-side lock enforcement
    # We will try to run another query with a different database_id,
    # and verify that it overrides it with the locked database connection ID.
    other_db_id = uuid.uuid4()

    # Reset mock
    mock_run_rag.reset_mock()
    mock_run_rag.side_effect = mock_generator

    body_override = QueryRequest(content="Show more data", database_id=other_db_id)

    response_override = await send_query(
        session_id=query_session.id, body=body_override, current_user=user, db=session
    )

    async for chunk in response_override.body_iterator:
        pass

    # Verify run_rag_pipeline was called with the locked database ID, overriding other_db_id!
    called_kwargs = mock_run_rag.call_args[1]
    assert called_kwargs["database_id"] == db_conn.id
