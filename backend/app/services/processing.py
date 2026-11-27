"""Submission processing: queueing, status transitions and the job bodies.

Status changes use compare-and-set updates, so a submission can be claimed by
only one worker at a time and repeated requests cannot process it twice.
Students only ever see the plain-language `status_message`; provider error
details go to the teacher-only `processing_error`.
"""

import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.models.ai import ModelSlot
from app.models.evaluation import ExtractedAnswer
from app.models.exam import Exam, Question, Rubric
from app.models.submission import Submission, SubmissionStatus as S
from app.providers.base import AIConfigurationError, AIError
from app.models.evaluation import Evaluation, EvaluationCriterion, EvaluationQuestion
from app.services import ai_router, evaluation_runner, extraction, verification

logger = logging.getLogger("gradepilot.processing")

MESSAGES = {
    S.QUEUED: "Waiting to be processed.",
    S.EXTRACTING: "Reading your script.",
    S.OCR_REVIEW_REQUIRED: "Your teacher is checking how your script was read.",
    S.READY_FOR_EVALUATION: "Your script has been read and is ready for marking.",
    S.EVALUATING: "Your answers are being marked.",
    S.VERIFYING: "Your marks are being checked.",
    S.APPROVED: "Marking is complete. Your teacher will release the results.",
    S.TEACHER_REVIEW_REQUIRED: "Marking is complete and waiting for your teacher's review.",
    S.FAILED: "Processing could not finish. Your teacher has been notified.",
}

# Where a full run (extract, then evaluate) may start from.
PROCESSABLE = (S.UPLOADED, S.FAILED, S.OCR_REVIEW_REQUIRED, S.READY_FOR_EVALUATION, S.TEACHER_REVIEW_REQUIRED)
# Where marking alone may start from (answers already extracted).
EVALUABLE = (S.READY_FOR_EVALUATION, S.OCR_REVIEW_REQUIRED, S.TEACHER_REVIEW_REQUIRED, S.FAILED)
IN_PROGRESS = (S.QUEUED, S.EXTRACTING, S.EVALUATING, S.VERIFYING)


def transition(db: Session, submission_id: uuid.UUID, allowed: tuple[S, ...], target: S, *,
               error: str | None = None, notes: str | None = None, keep_notes: bool = True) -> bool:
    values: dict = {"status": target.value, "status_message": MESSAGES.get(target), "processing_error": error}
    if not keep_notes:
        values["extraction_notes"] = notes
    result = db.execute(
        update(Submission)
        .where(Submission.id == submission_id, Submission.status.in_([s.value for s in allowed]))
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


def _load(db: Session, submission_id: uuid.UUID) -> Submission | None:
    db.expire_all()
    return db.scalar(
        select(Submission).where(Submission.id == submission_id).options(
            selectinload(Submission.files),
            selectinload(Submission.exam).selectinload(Exam.questions).selectinload(Question.children),
            selectinload(Submission.exam).selectinload(Exam.questions).selectinload(Question.model_answer),
            selectinload(Submission.exam).selectinload(Exam.questions).selectinload(Question.rubric).selectinload(Rubric.criteria),
        )
    )


def _fail(db: Session, submission_id: uuid.UUID, from_status: S, exc: Exception) -> None:
    db.rollback()
    detail = exc.message if isinstance(exc, AIError) else "An unexpected error occurred while processing."
    if not isinstance(exc, AIError):
        logger.exception("Processing failed for submission %s", submission_id)
    transition(db, submission_id, (from_status,), S.FAILED, error=detail)


def has_extracted_answers(db: Session, submission_id: uuid.UUID) -> bool:
    return db.scalar(select(ExtractedAnswer.id).where(ExtractedAnswer.submission_id == submission_id)) is not None


# --- Job bodies (run by the worker) ----------------------------------------

def run_evaluation(db: Session, submission_id: uuid.UUID) -> None:
    if not transition(db, submission_id, (S.QUEUED, S.READY_FOR_EVALUATION), S.EVALUATING):
        return  # already claimed or no longer eligible
    submission = _load(db, submission_id)
    if submission is None:
        return
    try:
        evaluation = evaluation_runner.evaluate(db, submission)
        db.commit()
        evaluation_id = evaluation.id
    except Exception as exc:  # noqa: BLE001 - every failure must leave a visible status
        _fail(db, submission_id, S.EVALUATING, exc)
        return
    if transition(db, submission_id, (S.EVALUATING,), S.VERIFYING):
        _verify(db, submission_id, evaluation_id)


def _load_evaluation(db: Session, evaluation_id: uuid.UUID) -> Evaluation | None:
    db.expire_all()
    return db.scalar(
        select(Evaluation).where(Evaluation.id == evaluation_id).options(
            selectinload(Evaluation.questions).selectinload(EvaluationQuestion.criteria).selectinload(EvaluationCriterion.evidence),
            selectinload(Evaluation.questions).selectinload(EvaluationQuestion.criteria).selectinload(EvaluationCriterion.rubric_criterion),
            selectinload(Evaluation.questions).selectinload(EvaluationQuestion.verification),
        )
    )


def _verify(db: Session, submission_id: uuid.UUID, evaluation_id: uuid.UUID) -> None:
    """Checks never fail a submission: problems become review flags."""
    try:
        _load(db, submission_id)  # loads the exam tree the checks need
        evaluation = _load_evaluation(db, evaluation_id)
        if evaluation is not None:
            verification.verify(db, evaluation)
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Verification failed for evaluation %s", evaluation_id)
    transition(db, submission_id, (S.VERIFYING,), S.TEACHER_REVIEW_REQUIRED)


def run_verification(db: Session, submission_id: uuid.UUID) -> None:
    if not transition(db, submission_id, (S.QUEUED,), S.VERIFYING):
        return
    evaluation_id = db.scalar(
        select(Evaluation.id).where(Evaluation.submission_id == submission_id, Evaluation.is_current.is_(True))
    )
    if evaluation_id is None:
        transition(db, submission_id, (S.VERIFYING,), S.TEACHER_REVIEW_REQUIRED)
        return
    _verify(db, submission_id, evaluation_id)


def run_processing(db: Session, submission_id: uuid.UUID) -> None:
    if not transition(db, submission_id, (S.QUEUED,), S.EXTRACTING):
        return
    submission = _load(db, submission_id)
    if submission is None:
        return
    try:
        outcome = extraction.extract(db, submission)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        _fail(db, submission_id, S.EXTRACTING, exc)
        return

    notes = "\n\n".join(outcome.notes) or None
    if outcome.needs_review:
        transition(db, submission_id, (S.EXTRACTING,), S.OCR_REVIEW_REQUIRED, notes=notes, keep_notes=False)
        return
    transition(db, submission_id, (S.EXTRACTING,), S.READY_FOR_EVALUATION, notes=notes, keep_notes=False)
    run_evaluation(db, submission_id)


# --- Queueing (called from API requests) -----------------------------------

def _dispatch(task_name: str, submission_id: uuid.UUID) -> None:
    from app.tasks import jobs

    getattr(jobs, task_name).delay(str(submission_id))


def queue_verification(db: Session, submission: Submission) -> None:
    if not transition(db, submission.id, (S.TEACHER_REVIEW_REQUIRED,), S.QUEUED):
        raise AppError(409, "Only evaluations waiting for review can be checked again")
    try:
        _dispatch("verify_submission", submission.id)
    except Exception:  # noqa: BLE001
        logger.exception("Could not queue verification for %s", submission.id)
        transition(db, submission.id, (S.QUEUED,), S.TEACHER_REVIEW_REQUIRED)
        raise AppError(503, "The job queue is unavailable. Try again shortly.") from None


def queue(db: Session, submission: Submission, *, evaluate_only: bool = False) -> None:
    """Queue a submission for processing, or raise an AppError explaining why not."""
    teacher_id = submission.exam.teacher_id
    if not ai_router.has_slot(db, teacher_id, ModelSlot.EVALUATOR):
        raise AppError(409, "Set up an evaluator model in AI Settings before processing submissions.")
    if S(submission.status) in IN_PROGRESS:
        raise AppError(409, "This submission is already being processed.")
    if evaluate_only and not has_extracted_answers(db, submission.id):
        raise AppError(409, "Extract the answers before marking this submission.")

    allowed = EVALUABLE if evaluate_only else PROCESSABLE
    if not transition(db, submission.id, allowed, S.QUEUED):
        raise AppError(409, "This submission cannot be processed in its current state.")
    try:
        _dispatch("evaluate_submission" if evaluate_only else "process_submission", submission.id)
    except Exception:  # noqa: BLE001 - e.g. the broker is unreachable
        logger.exception("Could not queue submission %s", submission.id)
        transition(db, submission.id, (S.QUEUED,), S.FAILED, error="The job queue is unavailable. Try again shortly.")
        raise AppError(503, "The job queue is unavailable. Try again shortly.") from None


def queue_on_upload(db: Session, submission: Submission) -> None:
    """Start processing a new submission automatically when the teacher has AI set up."""
    if not ai_router.has_slot(db, submission.exam.teacher_id, ModelSlot.EVALUATOR):
        return
    try:
        queue(db, submission)
    except AppError as exc:
        logger.info("Submission %s not queued automatically: %s", submission.id, exc.detail)


__all__ = ["AIConfigurationError", "queue", "queue_on_upload", "run_evaluation", "run_processing", "transition"]
