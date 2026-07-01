import os
import threading
import time
import logging
import uvicorn
from alembic.config import Config
from alembic import command
from app.celery_app import celery_app
from celery.beat import PersistentScheduler # type: ignore
from celery.apps.beat import Beat # type: ignore

# Explicitly import all task modules to guarantee registration in the main process
import app.tasks.document_tasks
import app.tasks.billing_tasks
import app.tasks.evaluation_tasks  # noqa: F401

logger = logging.getLogger("run")


def start_celery_worker():
    # Wait a small delay to ensure the main process has fully imported celery_app and task modules
    time.sleep(1.0)

    # Startup log listing all registered tasks
    registered_tasks = sorted(list(celery_app.tasks.keys()))
    logger.info(f"Celery worker initialized. Registered tasks: {registered_tasks}")

    celery_app.worker_main(
        argv=["worker", "--loglevel=info", "--pool=solo", "--concurrency=1"]
    )


def start_celery_beat():
    beat = Beat(app=celery_app, loglevel="info", scheduler=PersistentScheduler)
    beat.run()


if __name__ == "__main__":
    # Run migrations
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    # Start Celery worker in background thread
    worker_thread = threading.Thread(target=start_celery_worker, daemon=True)
    worker_thread.start()

    # Start Celery beat in background thread
    beat_thread = threading.Thread(target=start_celery_beat, daemon=True)
    beat_thread.start()

    # Start Uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
