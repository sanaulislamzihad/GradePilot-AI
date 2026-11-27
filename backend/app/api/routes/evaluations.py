"""Teacher-only processing actions, extracted answers and AI evaluation results.

Students never reach these endpoints: AI marks are suggestions until a teacher
reviews and publishes them (Phases 5 and 6).
"""

import uuid

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Client, DbSession, TeacherUser, rate_limit_ai
from app.core.errors import AppError
from app.models.audit_log import AuditLog
from app.models.evaluation import (
    AnswerStatus,
    Evaluation,
    EvaluationCriterion,
    EvaluationQuestion,
    ExtractedAnswer,
    ExtractionSource,
    ReviewStatus,
)
from app.models.user import User
from app.models.exam import Exam, ExamStatus, Question
from app.models.submission import Submission, SubmissionStatus as S
from app.schemas.evaluation import (
    BulkApproveResult,
    EvaluationCriterionRead,
    EvaluationQuestionRead,
    EvaluationQueueItem,
    EvaluationRead,
    EvidenceRead,
    ExtractedAnswerRead,
    ExtractedAnswersUpdate,
    ExtractionView,
    HistoryEntry,
    ProcessPendingResult,
    RejectRequest,
    ReviewUpdate,
    VerificationRead,
)
from app.schemas.submission import SubmissionDetail
from app.services import audit, processing, review
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

@router.post("/submissions/{submission_id}/extract", response_model=SubmissionDetail, dependencies=[Depends(rate_limit_ai)])
def extract_submission(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> SubmissionDetail:
    """Read the script and split it by question; marking follows automatically when nothing needs review."""
    submission = _owned_submission(db, teacher, submission_id)
    _record(db, teacher, "submission.process", submission, client)
    processing.queue(db, submission)
    return _detail(db, teacher, submission_id)


@router.post("/submissions/{submission_id}/retry", response_model=SubmissionDetail, dependencies=[Depends(rate_limit_ai)])
def retry_submission(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> SubmissionDetail:
    submission = _owned_submission(db, teacher, submission_id)
    if submission.status != S.FAILED.value:
        raise AppError(409, "Only failed submissions can be retried")
    _record(db, teacher, "submission.process", submission, client)
    processing.queue(db, submission)
    return _detail(db, teacher, submission_id)


@router.post("/submissions/{submission_id}/evaluate", response_model=SubmissionDetail, dependencies=[Depends(rate_limit_ai)])
def evaluate_submission(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> SubmissionDetail:
    """Mark the already-extracted answers again (for example after correcting them)."""
    submission = _owned_submission(db, teacher, submission_id)
    _record(db, teacher, "submission.evaluate", submission, client)
    processing.queue(db, submission, evaluate_only=True)
    return _detail(db, teacher, submission_id)


@router.post("/exams/{exam_id}/process-pending", response_model=ProcessPendingResult, dependencies=[Depends(rate_limit_ai)])
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


# --- Evaluation results and teacher review ---------------------------------

_EVAL_LOAD = (
    selectinload(Evaluation.questions).selectinload(EvaluationQuestion.criteria).selectinload(EvaluationCriterion.evidence),
    selectinload(Evaluation.questions).selectinload(EvaluationQuestion.criteria).selectinload(EvaluationCriterion.rubric_criterion),
    selectinload(Evaluation.questions).selectinload(EvaluationQuestion.verification),
)


def _verification_read(v) -> VerificationRead | None:
    if v is None:
        return None
    return VerificationRead(
        provider=v.provider, model=v.model, same_model_as_evaluator=v.same_model_as_evaluator,
        verdict=v.verdict, suggested_awarded=v.suggested_awarded, rubric_followed=v.rubric_followed,
        evidence_supports_marks=v.evidence_supports_marks, missed_valid_concepts=v.missed_valid_concepts,
        unsupported_assumptions=v.unsupported_assumptions, criterion_notes=v.criterion_notes, comment=v.comment,
    )


def _evaluation_read(db: Session, evaluation: Evaluation) -> EvaluationRead:
    answers = {
        a.question_id: a.text
        for a in db.scalars(select(ExtractedAnswer).where(ExtractedAnswer.submission_id == evaluation.submission_id))
    }
    types = dict(db.execute(
        select(Question.id, Question.question_type).where(Question.id.in_([q.question_id for q in evaluation.questions]))
    ).all())
    reviewer = db.get(User, evaluation.reviewed_by_id) if evaluation.reviewed_by_id else None
    return EvaluationRead(
        id=evaluation.id, submission_id=evaluation.submission_id, run_number=evaluation.run_number,
        is_current=evaluation.is_current, status=evaluation.status,
        provider=evaluation.provider, model=evaluation.model, total_awarded=evaluation.total_awarded,
        total_max=evaluation.total_max, final_total=evaluation.final_total, flags=evaluation.flags,
        started_at=evaluation.started_at, completed_at=evaluation.completed_at,
        verification_status=evaluation.verification_status, review_status=evaluation.review_status,
        teacher_comment=evaluation.teacher_comment,
        reviewed_by=reviewer.full_name if reviewer else None, reviewed_at=evaluation.reviewed_at,
        questions=[
            EvaluationQuestionRead(
                question_id=q.question_id, label=q.label, question_type=types.get(q.question_id, "descriptive"),
                answer_status=q.answer_status, awarded=q.awarded, teacher_awarded=q.teacher_awarded,
                final_awarded=review.question_final(q), max_marks=q.max_marks, feedback=q.feedback,
                missing_concepts=q.missing_concepts, flags=q.flags, similarity=q.similarity, math_check=q.math_check,
                teacher_comment=q.teacher_comment, answer_text=answers.get(q.question_id),
                criteria=[
                    EvaluationCriterionRead(
                        id=c.id, name=c.name, max_marks=c.max_marks, awarded=c.awarded,
                        teacher_awarded=c.teacher_awarded, final_awarded=review.criterion_final(c),
                        explanation=c.explanation, missing_concepts=c.missing_concepts,
                        evidence=[EvidenceRead(quote=e.quote, found_in_answer=e.found_in_answer) for e in c.evidence],
                    )
                    for c in q.criteria
                ],
                verification=_verification_read(q.verification),
            )
            for q in evaluation.questions
        ],
    )


def _owned_evaluation(db: Session, teacher, evaluation_id: uuid.UUID) -> tuple[Evaluation, Submission]:
    evaluation = db.scalar(select(Evaluation).where(Evaluation.id == evaluation_id).options(*_EVAL_LOAD))
    if evaluation is None:
        raise AppError(404, "Evaluation not found")
    return evaluation, _owned_submission(db, teacher, evaluation.submission_id)


def _final_text(evaluation: Evaluation) -> str:
    return f"{evaluation.final_total.normalize():f}" if evaluation.final_total is not None else "-"


@router.get("/submissions/{submission_id}/evaluation", response_model=EvaluationRead)
def current_evaluation(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> EvaluationRead:
    _owned_submission(db, teacher, submission_id)
    evaluation = db.scalar(
        select(Evaluation).where(Evaluation.submission_id == submission_id, Evaluation.is_current.is_(True)).options(*_EVAL_LOAD)
    )
    if evaluation is None:
        raise AppError(404, "This submission has not been evaluated yet")
    return _evaluation_read(db, evaluation)


def _needs_attention(flags: list[str]) -> bool:
    return any(flag != "missing_answer" for flag in flags)


@router.get("/evaluations", response_model=list[EvaluationQueueItem])
def evaluation_queue(
    teacher: TeacherUser,
    db: DbSession,
    exam_id: uuid.UUID | None = None,
    review_status: ReviewStatus | None = None,
    flagged_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[EvaluationQueueItem]:
    """Current evaluations of the teacher's latest submissions; flagged pending reviews first."""
    query = (
        select(Evaluation, Submission, Exam, User)
        .join(Submission, Evaluation.submission_id == Submission.id)
        .join(Exam, Submission.exam_id == Exam.id)
        .join(User, Submission.student_id == User.id)
        .where(Exam.teacher_id == teacher.id, Evaluation.is_current.is_(True), Submission.is_latest.is_(True))
    )
    if exam_id:
        query = query.where(Exam.id == exam_id)
    if review_status:
        query = query.where(Evaluation.review_status == review_status.value)
    rows = db.execute(query.order_by(Evaluation.completed_at.desc()).limit(limit)).all()
    items = [
        EvaluationQueueItem(
            evaluation_id=e.id, submission_id=s.id, submission_code=s.code, submission_status=s.status,
            exam_id=x.id, exam_title=x.title, student_name=u.full_name, student_number=s.student_number,
            total_awarded=e.total_awarded, final_total=e.final_total, total_max=e.total_max, flags=e.flags,
            verification_status=e.verification_status, review_status=e.review_status, completed_at=e.completed_at,
        )
        for e, s, x, u in rows
    ]
    if flagged_only:
        items = [i for i in items if _needs_attention(i.flags)]
    items.sort(key=lambda i: (i.review_status != ReviewStatus.PENDING, not _needs_attention(i.flags)))
    return items


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationRead)
def get_evaluation(evaluation_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> EvaluationRead:
    evaluation, _ = _owned_evaluation(db, teacher, evaluation_id)
    return _evaluation_read(db, evaluation)


@router.put("/evaluations/{evaluation_id}/review", response_model=EvaluationRead)
def save_review(evaluation_id: uuid.UUID, data: ReviewUpdate, teacher: TeacherUser, db: DbSession, client: Client) -> EvaluationRead:
    """Teacher overrides and comments. The backend recalculates the final marks."""
    evaluation, submission = _owned_evaluation(db, teacher, evaluation_id)
    if submission.status != S.TEACHER_REVIEW_REQUIRED.value:
        raise AppError(409, "This submission is not waiting for review")
    changes = review.apply(evaluation, data.questions, data.teacher_comment, "teacher_comment" in data.model_fields_set)
    if changes:
        audit.record(db, "evaluation.review", actor=teacher, entity_type="evaluation", entity_id=evaluation.id,
                     details={"code": submission.code, "changes": [c.as_dict() for c in changes]},
                     ip_address=client.ip_address)
    db.commit()
    return _evaluation_read(db, evaluation)


@router.post("/evaluations/{evaluation_id}/approve", response_model=EvaluationRead)
def approve_evaluation(evaluation_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> EvaluationRead:
    evaluation, submission = _owned_evaluation(db, teacher, evaluation_id)
    if submission.status != S.TEACHER_REVIEW_REQUIRED.value:
        raise AppError(409, "This submission is not waiting for review")
    review.approve(evaluation, teacher.id)
    audit.record(db, "evaluation.approve", actor=teacher, entity_type="evaluation", entity_id=evaluation.id,
                 details={"code": submission.code, "final_total": _final_text(evaluation)}, ip_address=client.ip_address)
    db.commit()
    processing.transition(db, submission.id, (S.TEACHER_REVIEW_REQUIRED,), S.APPROVED)
    db.expire_all()
    return _evaluation_read(db, _owned_evaluation(db, teacher, evaluation_id)[0])


@router.post("/evaluations/{evaluation_id}/reopen", response_model=EvaluationRead)
def reopen_evaluation(evaluation_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> EvaluationRead:
    evaluation, submission = _owned_evaluation(db, teacher, evaluation_id)
    if evaluation.review_status != ReviewStatus.APPROVED.value or submission.status != S.APPROVED.value:
        raise AppError(409, "Only approved evaluations that are not yet published can be reopened")
    evaluation.review_status = ReviewStatus.PENDING.value
    evaluation.reviewed_at = None
    evaluation.reviewed_by_id = None
    audit.record(db, "evaluation.reopen", actor=teacher, entity_type="evaluation", entity_id=evaluation.id,
                 details={"code": submission.code}, ip_address=client.ip_address)
    db.commit()
    processing.transition(db, submission.id, (S.APPROVED,), S.TEACHER_REVIEW_REQUIRED)
    db.expire_all()
    return _evaluation_read(db, _owned_evaluation(db, teacher, evaluation_id)[0])


@router.post("/evaluations/{evaluation_id}/reject", response_model=SubmissionDetail, dependencies=[Depends(rate_limit_ai)])
def reject_evaluation(
    evaluation_id: uuid.UUID, data: RejectRequest, teacher: TeacherUser, db: DbSession, client: Client
) -> SubmissionDetail:
    """Send the answers back for a fresh AI marking run; the reason stays with the old run."""
    evaluation, submission = _owned_evaluation(db, teacher, evaluation_id)
    review.ensure_reviewable(evaluation)
    evaluation.review_status = ReviewStatus.REJECTED.value
    evaluation.teacher_comment = data.reason
    evaluation.reviewed_by_id = teacher.id
    audit.record(db, "evaluation.reject", actor=teacher, entity_type="evaluation", entity_id=evaluation.id,
                 details={"code": submission.code, "reason": data.reason[:300]}, ip_address=client.ip_address)
    db.commit()
    try:
        processing.queue(db, submission, evaluate_only=True)
    except AppError:
        evaluation.review_status = ReviewStatus.PENDING.value  # stay reviewable if marking cannot start
        db.commit()
        raise
    return _detail(db, teacher, submission.id)


@router.post("/evaluations/{evaluation_id}/verify", response_model=SubmissionDetail, dependencies=[Depends(rate_limit_ai)])
def verify_evaluation(evaluation_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> SubmissionDetail:
    """Run the independent checks again, for example after setting up a verifier model."""
    evaluation, submission = _owned_evaluation(db, teacher, evaluation_id)
    review.ensure_reviewable(evaluation)
    processing.queue_verification(db, submission)
    return _detail(db, teacher, submission.id)


@router.get("/evaluations/{evaluation_id}/history", response_model=list[HistoryEntry])
def evaluation_history(evaluation_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> list[HistoryEntry]:
    """Every teacher action on any marking run of this submission, newest first."""
    _, submission = _owned_evaluation(db, teacher, evaluation_id)
    run_ids = [str(i) for i in db.scalars(select(Evaluation.id).where(Evaluation.submission_id == submission.id))]
    entries = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "evaluation", AuditLog.entity_id.in_(run_ids))
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
    ).all()
    return [
        HistoryEntry(action=e.action, summary=audit.describe(e), actor_name=e.actor.full_name if e.actor else None,
                     changes=(e.details or {}).get("changes", []), created_at=e.created_at)
        for e in entries
    ]


@router.post("/exams/{exam_id}/approve-unflagged", response_model=BulkApproveResult)
def approve_unflagged(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> BulkApproveResult:
    """Approve every pending evaluation of an exam that has no review flags."""
    exam = get_owned_exam(db, teacher, exam_id)
    rows = db.execute(
        select(Evaluation, Submission)
        .join(Submission, Evaluation.submission_id == Submission.id)
        .where(Submission.exam_id == exam.id, Submission.is_latest.is_(True), Evaluation.is_current.is_(True),
               Evaluation.review_status == ReviewStatus.PENDING.value,
               Submission.status == S.TEACHER_REVIEW_REQUIRED.value)
        .options(selectinload(Evaluation.questions).selectinload(EvaluationQuestion.criteria))
    ).all()
    approved = skipped = 0
    for evaluation, submission in rows:
        if not review.is_clean(evaluation):
            skipped += 1
            continue
        review.approve(evaluation, teacher.id)
        audit.record(db, "evaluation.approve", actor=teacher, entity_type="evaluation", entity_id=evaluation.id,
                     details={"code": submission.code, "final_total": _final_text(evaluation), "bulk": True},
                     ip_address=client.ip_address)
        db.commit()
        processing.transition(db, submission.id, (S.TEACHER_REVIEW_REQUIRED,), S.APPROVED)
        approved += 1
    return BulkApproveResult(approved=approved, skipped=skipped)
