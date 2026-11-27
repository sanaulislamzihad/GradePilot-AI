"""Celery application.

Production uses Redis (CELERY_BROKER_URL=redis://...). Local development
defaults to a SQLite-backed broker so no extra service is needed.

Start a worker:
    celery -A app.tasks.celery_app worker --loglevel=info            # Linux / macOS
    celery -A app.tasks.celery_app worker --loglevel=info --pool=solo  # Windows
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("gradepilot", broker=settings.celery_broker_url, include=["app.tasks.jobs"])
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_ignore_result=True,
    # Re-deliver a job if a worker dies mid-way; status checks keep it idempotent.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_default_queue="gradepilot",
)
