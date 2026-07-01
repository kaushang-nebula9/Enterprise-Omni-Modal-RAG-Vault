import os
import threading
import uvicorn
from alembic.config import Config
from alembic import command
from app.celery_app import celery_app
from celery.beat import PersistentScheduler
from celery.apps.beat import Beat


def start_celery_worker():
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
