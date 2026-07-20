import sys
import os
import pytest
import uuid
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.models.user import User
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.external_database import (
    ExternalDatabaseConnection,
    DatabaseSchemaCache,
    DatabaseAccessPolicy,
)
from app.services.rag_service import run_rag_pipeline
from tests.test_usage_logs import MockStream, MockCrossEncoder

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


class MockMessages:
    def __init__(self):
        self.call_count = 0

    async def create(self, *args, **kwargs):
        self.call_count += 1
        prompt = kwargs.get("messages", [{}])[0].get("content", "")
        system = kwargs.get("system", "")

        # If this is the retry (prompt or system mentions access denied), return an authorized query
        if "access denied" in prompt.lower() or "access denied" in system.lower():
            sql = "SELECT id FROM users"
        else:
            # First attempt: return an unauthorized query accessing the 'password' column
            sql = "SELECT id, password FROM users"

        m_res = MagicMock()
        m_res.content = [MagicMock(text=sql)]
        m_res.usage = MagicMock(input_tokens=10, output_tokens=20)
        return m_res

    def stream(self, *args, **kwargs):
        return MockStream()


class MockAnthropicClient:
    def __init__(self):
        self.messages = MockMessages()


@pytest.mark.asyncio
async def test_run_rag_pipeline_access_denied_self_correction(db):
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

    # Create connection
    connection = ExternalDatabaseConnection(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Test External DB",
        engine="postgresql",
        host="localhost",
        port=5432,
        username="postgres",
        password="password",
        database_name="test_db",
    )
    db.add(connection)
    db.commit()

    # Create schema cache with columns including 'id' and 'password'
    schema_data = {
        "tables": [
            {
                "name": "users",
                "columns": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "password", "type": "VARCHAR"},
                ],
                "primary_key": ["id"],
                "foreign_keys": [],
            }
        ]
    }
    schema_cache = DatabaseSchemaCache(
        connection_id=connection.id, schema_data=schema_data
    )
    db.add(schema_cache)
    db.commit()

    # Create access policy restricting to 'id' only (password is NOT authorized)
    policy = DatabaseAccessPolicy(
        connection_id=connection.id, role_id=role.id, table_name="users", columns=["id"]
    )
    db.add(policy)
    db.commit()

    def mock_embed_text(text):
        return [0.1] * 1024

    def mock_search_vectors(*args, **kwargs):
        return []

    # Mock connection execution so we don't hit a real DB
    def mock_run_query(*args, **kwargs):
        return [{"id": 1}]

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
        patch(
            "app.services.database_service._get_async_anthropic_client",
            return_value=mock_client,
        ),
        patch(
            "app.services.database_service.run_query_on_connection",
            side_effect=mock_run_query,
        ),
    ):
        events = []
        async for event in run_rag_pipeline(
            "Who is the user?", user, db, database_id=connection.id
        ):
            events.append(event)

        # Inspect events to verify self-correction message and corrected SQL
        token_contents = [e["content"] for e in events if e["type"] == "token"]
        combined_text = "".join(token_contents)

        assert (
            "Access denied: Column 'password' on table 'users' is unauthorized."
            not in combined_text
        )
        assert (
            "Attempting self-correction to find an alternative authorized query path..."
            in combined_text
        )
        assert "SELECT id FROM users" in combined_text
        assert "Executing query..." in combined_text
