import logging
from datetime import datetime
from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.notification import Notification
from app.models.enums import NotificationType
from app.services.notification_service import create_notification
from app.services.billing_service import calculate_tenant_monthly_cost

logger = logging.getLogger(__name__)


@celery_app.task(name="check_tenant_budgets_task")
def check_tenant_budgets_task():
    """
    Periodic task to check all tenants' monthly costs against their budget limit.
    Logs warning and dispatches notifications if any tenant has exceeded their monthly budget limit.
    """
    logger.info("Starting check_tenant_budgets_task...")
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        start_of_month = datetime(now.year, now.month, 1, 0, 0, 0)

        tenants = db.query(Tenant).all()
        for tenant in tenants:
            cost = calculate_tenant_monthly_cost(db, tenant.id)
            logger.info(
                f"Tenant '{tenant.name}' ({tenant.id}) current month cost: ${cost:.4f}"
            )
            if tenant.monthly_budget_limit is not None:
                if cost > tenant.monthly_budget_limit:
                    logger.warning(
                        f"Tenant '{tenant.name}' ({tenant.id}) has exceeded monthly budget limit! "
                        f"Cost: ${cost:.4f}, Limit: ${tenant.monthly_budget_limit:.2f}"
                    )

                    # Fetch all admins for this tenant
                    admins = (
                        db.query(User)
                        .join(Role)
                        .filter(User.tenant_id == tenant.id, Role.is_admin == True)
                        .all()
                    )

                    for admin in admins:
                        # Check if this admin has already been notified about budget_exceeded this calendar month for the CURRENT budget limit
                        limit_str = f"Limit: ${tenant.monthly_budget_limit:.2f}"
                        already_notified = (
                            db.query(Notification)
                            .filter(
                                Notification.user_id == admin.id,
                                Notification.type == NotificationType.budget_exceeded,
                                Notification.created_at >= start_of_month,
                                Notification.message.like(f"%{limit_str}%"),
                            )
                            .first()
                            is not None
                        )

                        if not already_notified:
                            msg = (
                                f"Your organization '{tenant.name}' has exceeded its monthly budget limit. "
                                f"Current usage: ${cost:.2f} (Limit: ${tenant.monthly_budget_limit:.2f})"
                            )
                            create_notification(
                                db=db,
                                user_id=admin.id,
                                tenant_id=tenant.id,
                                type=NotificationType.budget_exceeded,
                                message=msg,
                            )
    except Exception as e:
        logger.error(f"Error in check_tenant_budgets_task: {str(e)}")
    finally:
        db.close()
    logger.info("Finished check_tenant_budgets_task.")
