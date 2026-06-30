import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.notification import Notification
from app.models.enums import NotificationType
from app.services.notification_service import (
    create_notification,
    register_connection,
    unregister_connection,
)
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
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_notification_model_and_service(db):
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    # 1. Register queue connection
    queue = register_connection(user_id)

    # 2. Trigger notification
    notif = create_notification(
        db=db,
        user_id=user_id,
        tenant_id=tenant_id,
        type=NotificationType.role_assigned,
        message="You have been assigned the role: Test",
    )

    assert notif.id is not None
    assert notif.is_read is False

    # Query check
    db_notif = db.query(Notification).filter(Notification.id == notif.id).first()
    assert db_notif is not None
    assert db_notif.message == "You have been assigned the role: Test"

    # SSE Queue check
    assert not queue.empty()
    payload = queue.get_nowait()
    assert payload["id"] == str(notif.id)
    assert payload["message"] == "You have been assigned the role: Test"
    assert payload["type"] == "role_assigned"

    # Cleanup connection
    unregister_connection(user_id, queue)
