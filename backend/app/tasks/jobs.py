"""Background jobs. Each one is safe to run twice: it claims the submission
with a status check first and does nothing if another run already has it."""

import uuid

from app.database.session import SessionLocal
from app.services import processing
from app.tasks.celery_app import celery_app


@celery_app.task(name="gradepilot.process_submission")
def process_submission(submission_id: str) -> None:
    with SessionLocal() as db:
        processing.run_processing(db, uuid.UUID(submission_id))


@celery_app.task(name="gradepilot.evaluate_submission")
def evaluate_submission(submission_id: str) -> None:
    with SessionLocal() as db:
        processing.run_evaluation(db, uuid.UUID(submission_id))


@celery_app.task(name="gradepilot.verify_submission")
def verify_submission(submission_id: str) -> None:
    with SessionLocal() as db:
        processing.run_verification(db, uuid.UUID(submission_id))
