import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.models.document import Document
from app.models.enums import FileType, DocumentStatus, OwnerType, Visibility
from app.api.v1.chat import parse_chat_command

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


def test_parse_summarize_no_question(db):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    role_id = uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        role_id=role_id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="some_hash",
    )
    db.add(user)
    db.commit()

    # Without attachment
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/summarize", db, user, None
    )
    assert disp == "/summarize"
    assert ret == "Summarize conversation"
    assert "conversation history" in inst
    assert cmp_ids is None
    assert is_cmp is False
    assert is_sum is True

    # With attachment
    doc_id = uuid.uuid4()
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/summarize", db, user, doc_id
    )
    assert disp == "/summarize"
    assert ret == "Summarize this document"
    assert "overall purpose or subject" in inst
    assert cmp_ids is None
    assert is_cmp is False
    assert is_sum is True


def test_parse_summarize_with_question(db):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    role_id = uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        role_id=role_id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="some_hash",
    )

    from app.api.v1.chat import SUMMARIZE_FOCUSED_INSTRUCTION

    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/summarize How to build a RAG?", db, user, None
    )
    assert disp == "/summarize How to build a RAG?"
    assert ret == "How to build a RAG?"
    assert inst == SUMMARIZE_FOCUSED_INSTRUCTION
    assert cmp_ids is None
    assert is_cmp is False
    assert is_sum is False


def test_parse_other_prefix_commands(db):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    role_id = uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        role_id=role_id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="some_hash",
    )

    # Detailed
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/detailed How does it work?", db, user, None
    )
    assert disp == "/detailed How does it work?"
    assert ret == "How does it work?"
    assert "thorough" in inst
    assert is_cmp is False

    # Table
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/table list of users", db, user, None
    )
    assert disp == "/table list of users"
    assert "table" in inst

    # Bullets
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/bullets items to buy", db, user, None
    )
    assert disp == "/bullets items to buy"
    assert "bullet points" in inst

    # ELI5
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/eli5 quantum computing", db, user, None
    )
    assert disp == "/eli5 quantum computing"
    assert "simple" in inst
    assert "no background" in inst


def test_parse_compare_documents(db):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    role_id = uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        role_id=role_id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="some_hash",
    )
    db.add(user)

    # Create dummy documents
    doc1 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        uploaded_by=user_id,
        filename="ReportA.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.private,
        visibility=Visibility.private,
        qdrant_collection=f"tenant_{tenant_id}",
        status=DocumentStatus.ready,
        chunk_count=0,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        uploaded_by=user_id,
        filename="ReportB.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.private,
        visibility=Visibility.private,
        qdrant_collection=f"tenant_{tenant_id}",
        status=DocumentStatus.ready,
        chunk_count=0,
    )
    db.add_all([doc1, doc2])
    db.commit()

    # Compare without question
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/compare [ReportA.pdf] [ReportB.pdf]", db, user, None
    )
    assert disp == "/compare [ReportA.pdf] [ReportB.pdf]"
    assert ret == "Compare ReportA.pdf and ReportB.pdf"
    assert "direct comparison between two specific documents" in inst
    assert doc1.id in cmp_ids
    assert doc2.id in cmp_ids
    assert is_cmp is True

    # Compare with question
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/compare [ReportA.pdf] [ReportB.pdf] What are the differences in revenue?",
        db,
        user,
        None,
    )
    assert (
        disp
        == "/compare [ReportA.pdf] [ReportB.pdf] What are the differences in revenue?"
    )
    assert ret == "What are the differences in revenue?"
    assert "direct comparison between two specific documents" in inst
    assert doc1.id in cmp_ids
    assert doc2.id in cmp_ids
    assert is_cmp is True


def test_parse_multiple_commands(db):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    role_id = uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        role_id=role_id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="some_hash",
    )

    # Multiple style commands
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/detailed /table /bullets What are the requirements?", db, user, None
    )
    assert disp == "/detailed /table /bullets What are the requirements?"
    assert ret == "What are the requirements?"
    assert "thorough" in inst
    assert "table" in inst
    assert "bullet points" in inst
    assert is_cmp is False
    assert is_sum is False

    # Multiple commands empty query fallback (lead command detailed)
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/detailed /bullets", db, user, None
    )
    assert disp == "/detailed /bullets"
    assert ret == "Give a detailed answer"
    assert "thorough" in inst
    assert "bullet points" in inst
    assert is_cmp is False
    assert is_sum is False


def test_parse_compare_with_other_command(db):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    role_id = uuid.uuid4()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        role_id=role_id,
        email="test@example.com",
        full_name="Test User",
        hashed_password="some_hash",
    )
    db.add(user)

    doc1 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        uploaded_by=user_id,
        filename="ReportA.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.private,
        visibility=Visibility.private,
        qdrant_collection=f"tenant_{tenant_id}",
        status=DocumentStatus.ready,
        chunk_count=0,
    )
    doc2 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        uploaded_by=user_id,
        filename="ReportB.pdf",
        file_type=FileType.pdf,
        owner_type=OwnerType.private,
        visibility=Visibility.private,
        qdrant_collection=f"tenant_{tenant_id}",
        status=DocumentStatus.ready,
        chunk_count=0,
    )
    db.add_all([doc1, doc2])
    db.commit()

    # Compare with bullets and table
    disp, ret, inst, cmp_ids, is_cmp, is_sum = parse_chat_command(
        "/compare [ReportA.pdf] [ReportB.pdf] /bullets /table Compare revenues",
        db,
        user,
        None,
    )
    assert (
        disp == "/compare [ReportA.pdf] [ReportB.pdf] /bullets /table Compare revenues"
    )
    assert ret == "Compare revenues"
    assert "direct comparison between two specific documents" in inst
    assert "bullet points" in inst
    assert "table" in inst
    assert doc1.id in cmp_ids
    assert doc2.id in cmp_ids
    assert is_cmp is True
    assert is_sum is False
