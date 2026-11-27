"""Teacher-only processing actions, extracted answers and AI evaluation results.

Students never reach these endpoints: AI marks are suggestions until a teacher
reviews and publishes them (Phases 5 and 6).
"""

import uuid

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Client, DbSession, TeacherUser
from app.core.errors import AppError
from app.models.evaluation import (
    AnswerStatus,
    Evaluation,
    EvaluationCriterion,
    EvaluationQuestion,
    ExtractedAnswer,
    ExtractionSource,
)
from app.models.exam import Exam, ExamStatus, Question
from app.models.submission import Submission, SubmissionStatus as S
from app.schemas.evaluation import (
    EvaluationCriterionRead,
    EvaluationQuestionRead,
    EvaluationRead,
    EvidenceRead,
    ExtractedAnswerRead,
    ExtractedAnswersUpdate,
    ExtractionView,
    ProcessPendingResult,
)
from app.schemas.submission import SubmissionDetail
from app.services import audit, processing
from app.services import submission_service as subs
from app.services.exam_service import get_owned_exam, leaves

router = APIRouter(tags=["evaluation"])

EDITABLE_EXTRACTION = (S.OCR_REVIEW_REQUIRED, S.READY_FOR_EVALUATION, S.TEACHER_REVIEW_REQUIRED, S.FAILED)


def _owned_submission(db: Session, teacher, submission_id: uuid.UUID) -> Submission:
    submission = db.scalar(
        select(Submission).where(Submission.id == submission_id).options(
            selectinload(Submission.exam).selectinload(Exam.questions).selectinload(Question.children),
            selectinload(Submission.files), selectinload(Submission.student),
        )
    )
    if submission is None or submission.exam.teacher_id != teacher.id:
        raise AppError(404, "Submission not found")
    return submission


def _detail(db: Session, teacher, submission_id: uuid.UUID) -> SubmissionDetail:
    db.expire_all()
    return subs.detail(_owned_submission(db, teacher, submission_id), include_teacher_fields=True)


def _record(db, teacher, action: str, submission: Submission, client) -> None:
    audit.record(db, action, actor=teacher, entity_type="submission", entity_id=submission.id,
                 details={"code": submission.code}, ip_address=client.ip_address)
    db.commit()


# --- Processing actions ----------------------------------------------------

@router.post("/submissions/{submission_id}/extract", response_model=SubmissionDetail)
def extract_submission(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> SubmissionDetail:
    """Read the script and split it by question; marking follows automatically when nothing needs review."""
    submission = _owned_submission(db, teacher, submission_id)
    _record(db, teacher, "submission.process", submission, client)
    processing.queue(db, submission)
    return _detail(db, teacher, submission_id)


@router.post("/submissions/{submission_id}/retry", response_model=SubmissionDetail)
def retry_submission(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> SubmissionDetail:
    submission = _owned_submission(db, teacher, submission_id)
    if submission.status != S.FAILED.value:
        raise AppError(409, "Only failed submissions can be retried")
    _record(db, teacher, "submission.process", submission, client)
    processing.queue(db, submission)
    return _detail(db, teacher, submission_id)


@router.post("/submissions/{submission_id}/evaluate", response_model=SubmissionDetail)
def evaluate_submission(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> SubmissionDetail:
    """Mark the already-extracted answers again (for example after correcting them)."""
    submission = _owned_submission(db, teacher, submission_id)
    _record(db, teacher, "submission.evaluate", submission, client)
    processing.queue(db, submission, evaluate_only=True)
    return _detail(db, teacher, submission_id)


@router.post("/exams/{exam_id}/process-pending", response_model=ProcessPendingResult)
def process_pending(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> ProcessPendingResult:
    """Queue every current submission of an exam that has not been processed or has failed."""
    exam = get_owned_exam(db, teacher, exam_id)
    if exam.status != ExamStatus.PUBLISHED.value:
        raise AppError(409, "Only published exams have submissions to process")
    pending = db.scalars(
        select(Submission).where(
            Submission.exam_id == exam.id, Submission.is_latest.is_(True),
            Submission.status.in_([S.UPLOADED.value, S.FAILED.value]),
        ).options(selectinload(Submission.exam))
    ).all()
    queued = skipped = 0
    for submission in pending:
        try:
            processing.queue(db, submission)
            queued += 1
        except AppError as exc:
            if exc.status_code == 409 and "evaluator" in exc.detail:
                raise
            skipped += 1
    return ProcessPendingResult(queued=queued, skipped=skipped)


# --- Extracted answers -----------------------------------------------------

def _extraction_view(db: Session, submission: Submission) -> ExtractionView:
    answers = {
        a.question_id: a
        for a in db.scalars(select(ExtractedAnswer).where(ExtractedAnswer.submission_id == submission.id))
    }
    rows = []
    for question, label in leaves(submission.exam):
        answer = answers.get(question.id)
        if answer is None:
            continue
        rows.append(ExtractedAnswerRead(
            question_id=question.id, label=label, question_text=question.text, max_marks=question.marks,
            text=answer.text, status=answer.status, source=answer.source,  # type: ignore[arg-type]
            confidence=answer.confidence, pages=answer.pages, unreadable_notes=answer.unreadable_notes,
            needs_review=answer.needs_review,
        ))
    return ExtractionView(status=submission.status, extraction_notes=submission.extraction_notes, answers=rows)


@router.get("/submissions/{submission_id}/extracted-answers", response_model=ExtractionView)
def get_extracted_answers(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> ExtractionView:
    return _extraction_view(db, _owned_submission(db, teacher, submission_id))


@router.put("/submissions/{submission_id}/extracted-answers", response_model=ExtractionView)
def correct_extracted_answers(
    submission_id: uuid.UUID, data: ExtractedAnswersUpdate, teacher: TeacherUser, db: DbSession, client: Client
) -> ExtractionView:
    """Teacher corrections to the transcription. Corrected text is trusted as written."""
    submission = _owned_submission(db, teacher, submission_id)
    if S(submission.status) not in EDITABLE_EXTRACTION:
        raise AppError(409, "Answers can be corrected only after extraction and while no processing is running")
    answers = {
        a.question_id: a
        for a in db.scalars(select(ExtractedAnswer).where(ExtractedAnswer.submission_id == submission.id))
    }
    if not answers:
        raise AppError(409, "This submission has not been extracted yet")

    gradable = {question.id for question, _ in leaves(submission.exam)}
    for item in data.answers:
        if item.question_id not in gradable:
            raise AppError(422, "One of the answers does not belong to a question of this exam")
        answer = answers.get(item.question_id)
        if answer is None:
            answer = ExtractedAnswer(submission_id=submission.id, question_id=item.question_id, pages=[], unreadable_notes=[])
            db.add(answer)
        text = item.text.strip()
        status_value = item.status
        if status_value == AnswerStatus.ANSWERED and not text:
            status_value = AnswerStatus.MISSING
        answer.text = text if status_value == AnswerStatus.ANSWERED else ""
        answer.status = status_value.value
        answer.source = ExtractionSource.TEACHER.value
        answer.confidence = 1.0
        answer.needs_review = status_value == AnswerStatus.UNREADABLE

    audit.record(db, "submission.extraction_corrected", actor=teacher, entity_type="submission",
                 entity_id=submission.id, details={"code": submission.code, "answers": len(data.answers)},
                 ip_address=client.ip_address)
    db.commit()
    if data.confirm and submission.status == S.OCR_REVIEW_REQUIRED.value:
        processing.transition(db, submission.id, (S.OCR_REVIEW_REQUIRED,), S.READY_FOR_EVALUATION)
    db.expire_all()
    return _extraction_view(db, _owned_submission(db, teacher, submission_id))


# --- Evaluation results ----------------------------------------------------

def _evaluation_read(db: Session, evaluation: Evaluation) -> EvaluationRead:
    answers = {
        a.question_id: a.text
        for a in db.scalars(select(ExtractedAnswer).where(ExtractedAnswer.submission_id == evaluation.submission_id))
    }
    return EvaluationRead(
        id=evaluation.id, submission_id=evaluation.submission_id, run_number=evaluation.run_number,
        is_current=evaluation.is_current, status=evaluation.status,  # type: ignore[arg-type]
        provider=evaluation.provider, model=evaluation.model, total_awarded=evaluation.total_awarded,
        total_max=evaluation.total_max, flags=evaluation.flags, started_at=evaluation.started_at,
        completed_at=evaluation.completed_at,
        questions=[
            EvaluationQuestionRead(
                question_id=q.question_id, label=q.label, answer_status=q.answer_status,  # type: ignore[arg-type]
                awarded=q.awarded, max_marks=q.max_marks, feedback=q.feedback, missing_concepts=q.missing_concepts,
                flags=q.flags, answer_text=answers.get(q.question_id),
                criteria=[
                    EvaluationCriterionRead(
                        name=c.name, max_marks=c.max_marks, awarded=c.awarded, explanation=c.explanation,
                        missing_concepts=c.missing_concepts,
                        evidence=[EvidenceRead(quote=e.quote, found_in_answer=e.found_in_answer) for e in c.evidence],
                    )
                    for c in q.criteria
                ],
            )
            for q in evaluation.questions
        ],
    )


_EVAL_LOAD = (
    selectinload(Evaluation.questions).selectinload(EvaluationQuestion.criteria).selectinload(EvaluationCriterion.evidence),
)


@router.get("/submissions/{submission_id}/evaluation", response_model=EvaluationRead)
def current_evaluation(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> EvaluationRead:
    _owned_submission(db, teacher, submission_id)
    evaluation = db.scalar(
        select(Evaluation).where(Evaluation.submission_id == submission_id, Evaluation.is_current.is_(True)).options(*_EVAL_LOAD)
    )
    if evaluation is None:
        raise AppError(404, "This submission has not been evaluated yet")
    return _evaluation_read(db, evaluation)


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationRead)
def get_evaluation(evaluation_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> EvaluationRead:
    evaluation = db.scalar(select(Evaluation).where(Evaluation.id == evaluation_id).options(*_EVAL_LOAD))
    if evaluation is None:
        raise AppError(404, "Evaluation not found")
    _owned_submission(db, teacher, evaluation.submission_id)
    return _evaluation_read(db, evaluation)

