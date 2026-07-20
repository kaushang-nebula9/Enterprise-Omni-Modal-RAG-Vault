import sys
import os
import uuid
import pytest
from datetime import datetime
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
from app.core.dependencies import get_current_user
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.query_session import QuerySession
from app.models.query_message import QueryMessage
from app.models.enums import MessageRole

DATABASE_URL = "sqlite:///:memory:"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


test_context = {"current_user": None, "db_session": None}


def override_get_db():
    yield test_context["db_session"]


def override_get_current_user():
    if not test_context["current_user"]:
        raise Exception("Current user not set in test context")
    return test_context["current_user"]


@pytest.fixture(autouse=True)
def configure_dependency_overrides():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


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


@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)


def test_search_conversations(db, client):
    # 1. Create Tenant & Users
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug="test-tenant")
    role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="Member")
    db.add_all([tenant, role])
    db.commit()

    user1 = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="user1@test.com",
        full_name="User One",
        hashed_password="pwd",
        role_id=role.id,
        is_active=True,
    )
    user2 = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="user2@test.com",
        full_name="User Two",
        hashed_password="pwd",
        role_id=role.id,
        is_active=True,
    )
    db.add_all([user1, user2])
    db.commit()

    # Log in user1
    test_context["current_user"] = user1

    # 2. Create Chat Sessions (Conversations) & Messages for User 1
    # Match in title
    session_title_match = QuerySession(
        id=uuid.uuid4(),
        user_id=user1.id,
        tenant_id=tenant.id,
        title="Learning Python Basics",
    )
    # Match in message content (with markdown)
    session_msg_match = QuerySession(
        id=uuid.uuid4(),
        user_id=user1.id,
        tenant_id=tenant.id,
        title="Other Topic",
    )
    msg_matching = QueryMessage(
        id=uuid.uuid4(),
        session_id=session_msg_match.id,
        role=MessageRole.user,
        content="* Let's write some python code\n- Python is fun!\n# Header text\n> A quote about python",
    )
    # No match
    session_no_match = QuerySession(
        id=uuid.uuid4(),
        user_id=user1.id,
        tenant_id=tenant.id,
        title="Something Else",
    )
    msg_no_match = QueryMessage(
        id=uuid.uuid4(),
        session_id=session_no_match.id,
        role=MessageRole.user,
        content="Hello world, this is a message with no keyword.",
    )

    # 3. Create Chat Session for User 2 (Should not be returned)
    session_user2_match = QuerySession(
        id=uuid.uuid4(),
        user_id=user2.id,
        tenant_id=tenant.id,
        title="Python query for User 2",
    )
    msg_user2 = QueryMessage(
        id=uuid.uuid4(),
        session_id=session_user2_match.id,
        role=MessageRole.user,
        content="Python is great",
    )

    db.add_all(
        [
            session_title_match,
            session_msg_match,
            msg_matching,
            session_no_match,
            msg_no_match,
            session_user2_match,
            msg_user2,
        ]
    )
    db.commit()

    # Test GET /api/conversations/search?q=python
    response = client.get("/api/conversations/search?q=python")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Should only return user1's matching conversations (session_title_match and session_msg_match)
    assert data["total_count"] == 2
    assert len(data["results"]) == 2
    assert data["has_more"] is False

    # Check results properties
    res_titles = [r["conversation_title"] for r in data["results"]]
    assert "Learning Python Basics" in res_titles
    assert "Other Topic" in res_titles
    assert "Something Else" not in res_titles
    assert "Python query for User 2" not in res_titles

    # Verify matching lines, match_count, and roles metadata in session_msg_match
    msg_match_res = next(
        r for r in data["results"] if r["conversation_title"] == "Other Topic"
    )
    assert msg_match_res["match_in_title"] is False
    assert msg_match_res["match_count"] == 3
    assert len(msg_match_res["matching_lines"]) == 3

    # Check roles and stripped markdown lines
    matching_texts = [line["text"] for line in msg_match_res["matching_lines"]]
    matching_roles = [line["role"] for line in msg_match_res["matching_lines"]]

    assert "Let's write some python code" in matching_texts
    assert "Python is fun!" in matching_texts
    assert "A quote about python" in matching_texts
    assert all(r == "user" for r in matching_roles)

    # Verify match_in_title and conversation_date
    title_match_res = next(
        r
        for r in data["results"]
        if r["conversation_title"] == "Learning Python Basics"
    )
    assert title_match_res["match_in_title"] is True
    assert title_match_res["conversation_date"] is not None

    # Test error cases
    # Empty query
    response_empty = client.get("/api/conversations/search?q=")
    assert response_empty.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    response_space = client.get("/api/conversations/search?q=%20%20")
    assert response_space.status_code == status.HTTP_400_BAD_REQUEST


def test_advanced_search_filters(db, client):
    # Setup Tenant, Users, Role
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug="test-tenant")
    role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="Member")
    db.add_all([tenant, role])
    db.commit()

    user1 = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="user1@test.com",
        full_name="User One",
        hashed_password="pwd",
        role_id=role.id,
        is_active=True,
    )
    db.add(user1)
    db.commit()

    test_context["current_user"] = user1

    # Create sessions with specific updated_at dates, titles, and message matches
    # Session 1: Oldest, matches in both
    session1 = QuerySession(
        id=uuid.uuid4(),
        user_id=user1.id,
        tenant_id=tenant.id,
        title="Python Intro Class",
        updated_at=datetime(2025, 1, 10, 10, 0, 0),
    )
    msg1 = QueryMessage(
        id=uuid.uuid4(),
        session_id=session1.id,
        role=MessageRole.user,
        content="I love Python programming!",
    )

    # Session 2: Mid-date, matches only in title
    session2 = QuerySession(
        id=uuid.uuid4(),
        user_id=user1.id,
        tenant_id=tenant.id,
        title="Python advanced tips",
        updated_at=datetime(2025, 6, 15, 12, 0, 0),
    )
    msg2 = QueryMessage(
        id=uuid.uuid4(),
        session_id=session2.id,
        role=MessageRole.assistant,
        content="Welcome to our class.",
    )

    # Session 3: Newest, matches only in messages, has multiple matches (most matches)
    session3 = QuerySession(
        id=uuid.uuid4(),
        user_id=user1.id,
        tenant_id=tenant.id,
        title="React and Web Dev",
        updated_at=datetime(2025, 12, 20, 15, 0, 0),
    )
    msg3_1 = QueryMessage(
        id=uuid.uuid4(),
        session_id=session3.id,
        role=MessageRole.user,
        content="Is python used in React?",
    )
    msg3_2 = QueryMessage(
        id=uuid.uuid4(),
        session_id=session3.id,
        role=MessageRole.assistant,
        content="No, python is backend, react is frontend.",
    )

    db.add_all([session1, msg1, session2, msg2, session3, msg3_1, msg3_2])
    db.commit()

    # 1. Test Date Range Filter
    # date_from = "2025-06-01"
    response = client.get("/api/conversations/search?q=python&date_from=2025-06-01")
    assert response.status_code == 200
    data = response.json()
    # Should only return session2 and session3 (dates: 2025-06-15 and 2025-12-20)
    assert data["total_count"] == 2
    titles = [r["conversation_title"] for r in data["results"]]
    assert "Python Intro Class" not in titles

    # date_to = "2025-07-01"
    response = client.get("/api/conversations/search?q=python&date_to=2025-07-01")
    assert response.status_code == 200
    data = response.json()
    # Should only return session1 and session2
    assert data["total_count"] == 2
    titles = [r["conversation_title"] for r in data["results"]]
    assert "React and Web Dev" not in titles

    # 2. Test match_in filter
    # match_in=titles (only matches session1 and session2 since session3's title is "React and Web Dev")
    response = client.get("/api/conversations/search?q=python&match_in=titles")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2
    titles = [r["conversation_title"] for r in data["results"]]
    assert "React and Web Dev" not in titles

    # match_in=messages (session1 and session3 have python in messages, session2 does not)
    response = client.get("/api/conversations/search?q=python&match_in=messages")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2
    titles = [r["conversation_title"] for r in data["results"]]
    assert "Python advanced tips" not in titles

    # 3. Test sort orders
    # sort=recent (session3 (Dec 20), session2 (Jun 15), session1 (Jan 10))
    response = client.get("/api/conversations/search?q=python&sort=recent")
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["conversation_title"] == "React and Web Dev"
    assert data["results"][1]["conversation_title"] == "Python advanced tips"
    assert data["results"][2]["conversation_title"] == "Python Intro Class"

    # sort=oldest (session1 (Jan 10), session2 (Jun 15), session3 (Dec 20))
    response = client.get("/api/conversations/search?q=python&sort=oldest")
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["conversation_title"] == "Python Intro Class"
    assert data["results"][1]["conversation_title"] == "Python advanced tips"
    assert data["results"][2]["conversation_title"] == "React and Web Dev"

    # sort=most_matches (session3 has 2 matches, session1 has 1, session2 has 0)
    response = client.get("/api/conversations/search?q=python&sort=most_matches")
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["conversation_title"] == "React and Web Dev"  # 2 matches
    assert data["results"][1]["conversation_title"] == "Python Intro Class"  # 1 match
    assert (
        data["results"][2]["conversation_title"] == "Python advanced tips"
    )  # 0 matches

    # 4. Test case_sensitive filter
    # case_sensitive=true, q="python" (only matches session3 which contains lowercase "python" in message)
    response = client.get("/api/conversations/search?q=python&case_sensitive=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1
    assert data["results"][0]["conversation_title"] == "React and Web Dev"

    # case_sensitive=true, q="Python" (matches session1 ("Python Intro Class") and session2 ("Python advanced tips"))
    response = client.get("/api/conversations/search?q=Python&case_sensitive=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 2
