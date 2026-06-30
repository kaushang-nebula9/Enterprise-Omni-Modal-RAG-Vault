import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from app.db.base import Base
from app.models.tenant import Tenant
from app.models.available_model import AvailableModel, ModelProvider
from app.models.usage_log import UsageLog
from app.services.billing_service import calculate_tenant_monthly_cost
from app.tasks.billing_tasks import check_tenant_budgets_task

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


DATABASE_URL = "sqlite:///:memory:"


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


def test_calculate_tenant_monthly_cost_configured_pricing(db):
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug="test-tenant")
    db.add(tenant)

    # Configure model pricing
    model = AvailableModel(
        id=uuid.uuid4(),
        display_name="Claude Test Model",
        provider=ModelProvider.anthropic,
        model_string="claude-test-model",
        is_active=True,
        input_price_per_million=Decimal("2.5000"),
        output_price_per_million=Decimal("10.0000"),
    )
    db.add(model)
    db.commit()

    # Add usage logs
    log1 = UsageLog(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=uuid.uuid4(),
        provider="anthropic",
        model_string="claude-test-model",
        input_tokens=2_000_000,  # Cost: 2 * 2.50 = 5.00
        output_tokens=500_000,  # Cost: 0.5 * 10.00 = 5.00
        created_at=datetime.utcnow(),
    )
    db.add(log1)
    db.commit()

    cost = calculate_tenant_monthly_cost(db, tenant.id)
    assert cost == 10.00


def test_calculate_tenant_monthly_cost_unconfigured_pricing(db):
    tenant = Tenant(id=uuid.uuid4(), name="Test Tenant", slug="test-tenant")
    db.add(tenant)

    # Model with null pricing
    model = AvailableModel(
        id=uuid.uuid4(),
        display_name="OpenRouter Test Model",
        provider=ModelProvider.openrouter,
        model_string="openrouter-test-model",
        is_active=True,
        input_price_per_million=None,
        output_price_per_million=None,
    )
    db.add(model)
    db.commit()

    # Add usage logs
    log1 = UsageLog(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=uuid.uuid4(),
        provider="openrouter",
        model_string="openrouter-test-model",
        input_tokens=2_000_000,
        output_tokens=500_000,
        created_at=datetime.utcnow(),
    )
    db.add(log1)
    db.commit()

    # Budget calculation should treat unconfigured prices as 0.0 (no $15/M fallback)
    cost = calculate_tenant_monthly_cost(db, tenant.id)
    assert cost == 0.00


@patch("app.tasks.billing_tasks.SessionLocal")
def test_check_tenant_budgets_task_warning(mock_session_local):
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name="Test Tenant",
        slug="test-tenant",
        monthly_budget_limit=100.00,
    )
    mock_db.query.return_value.all.return_value = [tenant]

    # Mock calculate_tenant_monthly_cost to return 120.00 (exceeds budget)
    with patch(
        "app.tasks.billing_tasks.calculate_tenant_monthly_cost", return_value=120.00
    ) as mock_cost_calc:
        with patch("app.tasks.billing_tasks.logger") as mock_logger:
            check_tenant_budgets_task()
            mock_cost_calc.assert_called_once_with(mock_db, tenant_id)
            mock_logger.warning.assert_called_once()
            assert (
                "exceeded monthly budget limit" in mock_logger.warning.call_args[0][0]
            )


from app.models.role import Role
from app.models.user import User
from app.models.notification import Notification
from app.models.enums import NotificationType


@patch("app.tasks.billing_tasks.SessionLocal")
def test_check_tenant_budgets_task_notification(mock_session_local, db):
    mock_session_local.return_value = db

    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Budget Tenant",
        slug="test-budget-tenant",
        monthly_budget_limit=10.00,
    )
    db.add(tenant)

    admin_role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="Admin", is_admin=True)
    db.add(admin_role)

    user_role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="User", is_admin=False)
    db.add(user_role)
    db.commit()

    admin_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="admin@test.com",
        full_name="Admin User",
        hashed_password="hash",
        role_id=admin_role.id,
    )
    db.add(admin_user)

    regular_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="user@test.com",
        full_name="Regular User",
        hashed_password="hash",
        role_id=user_role.id,
    )
    db.add(regular_user)
    db.commit()

    admin_user_id = admin_user.id

    # Mock calculate_tenant_monthly_cost to return 15.00 (exceeds budget limit 10.00)
    with patch.object(db, "close", return_value=None):
        with patch(
            "app.tasks.billing_tasks.calculate_tenant_monthly_cost", return_value=15.00
        ):
            check_tenant_budgets_task()

    # Check that a notification of type budget_exceeded was created for the admin user
    notifications = db.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].user_id == admin_user_id
    assert notifications[0].type == NotificationType.budget_exceeded
    assert "exceeded its monthly budget limit" in notifications[0].message

    # Run the budget check task again, it should NOT create a duplicate notification for the current month
    with patch.object(db, "close", return_value=None):
        with patch(
            "app.tasks.billing_tasks.calculate_tenant_monthly_cost", return_value=15.00
        ):
            check_tenant_budgets_task()

    notifications_after = db.query(Notification).all()
    assert len(notifications_after) == 1

    # Now update the monthly budget limit from 10.00 to 12.00
    tenant.monthly_budget_limit = 12.00
    db.commit()

    # Run the budget check task again with cost 14.00 (exceeds new limit 12.00)
    with patch.object(db, "close", return_value=None):
        with patch(
            "app.tasks.billing_tasks.calculate_tenant_monthly_cost", return_value=14.00
        ):
            check_tenant_budgets_task()

    # Check that a new notification has been created
    notifications_final = (
        db.query(Notification).order_by(Notification.created_at.asc()).all()
    )
    assert len(notifications_final) == 2
    assert notifications_final[1].user_id == admin_user_id
    assert notifications_final[1].type == NotificationType.budget_exceeded
    assert "Limit: $12.00" in notifications_final[1].message
