import app.db.base  # noqa: F401 - ensures all models are registered before tasks run
from celery import Celery  # type: ignore
from app.core.config import settings

celery_app = Celery(
    "rag_vault",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Cap Redis connections per process so we stay within the free-tier
    # client limit (Upstash free = ~100 simultaneous connections).
    # Default broker_pool_limit is 10 — with FastAPI + worker + Flower
    # all connected simultaneously that easily exceeds the limit.
    broker_pool_limit=2,
    redis_max_connections=5,
    beat_schedule={
        "check-tenant-budgets-hourly": {
            "task": "check_tenant_budgets_task",
            "schedule": 3600.0,
        }
    },
)
celery_app.autodiscover_tasks(["app.tasks"])

# Explicitly import task modules to guarantee registration regardless of autodiscovery timing
import app.tasks.document_tasks  # noqa: E402
import app.tasks.billing_tasks  # noqa: E402
import app.tasks.evaluation_tasks  # noqa: E402, F401
