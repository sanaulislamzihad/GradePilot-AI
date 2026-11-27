"""Result publication and the student-facing result view.

Only teacher-approved marks are ever published. In provisional mode, students
may also see the current AI marks once marking has finished, clearly labelled
as provisional. Student-facing data never includes AI provider details, review
flags, verification notes or anything the teacher has not chosen to release.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.database.base import utcnow
from app.models.evaluation import Evaluation, EvaluationQuestion, FinalResult, ReviewStatus
from app.models.exam import Exam, ResultReleaseMode
from app.models.submission import Submission, SubmissionStatus as S
from app.models.user import User
from app.schemas.results import ResultCriterion, ResultQuestion, ResultView
from app.services import review
from app.services.exam_service import leaves

PROVISIONAL_STATUSES = (S.TEACHER_REVIEW_REQUIRED.value, S.APPROVED.value)


def _num(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def percentage(total: Decimal, maximum: Decimal) -> Decimal:
    if not maximum:
        return Decimal("0")
    return (total / maximum * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def current_evaluation(db: Session, submission_id) -> Evaluation | None:
    return db.scalar(
        select(Evaluation)
        .where(Evaluation.submission_id == submission_id, Evaluation.is_current.is_(True))
        .options(selectinload(Evaluation.questions).selectinload(EvaluationQuestion.criteria))
    )


def build_snapshot(exam: Exam, evaluation: Evaluation, *, include_comments: bool) -> dict:
    """Student-facing copy of the marks, in paper order."""
    rows = {q.question_id: q for q in evaluation.questions}
    questions = []
    for question, label in leaves(exam):
        row = rows.get(question.id)
        if row is None:
            continue
        criteria = sorted(row.criteria, key=lambda c: c.position)
        questions.append({
            "label": label,
            "text": question.text,
            "max_marks": float(row.max_marks),
            "awarded": _num(review.question_final(row)),
            "answered": row.answer_status == "answered",
            "criteria": [
                {
                    "name": c.name,
                    "max_marks": float(c.max_marks),
                    "awarded": float(review.criterion_final(c)),
                    "explanation": c.explanation,
                    "missing_concepts": list(c.missing_concepts or []),
                }
                for c in criteria
            ],
            "feedback": row.feedback,
            "missing_concepts": list(row.missing_concepts or []),
            "teacher_comment": row.teacher_comment if include_comments else None,
        })
    return {
        "questions": questions,
        "teacher_comment": evaluation.teacher_comment if include_comments else None,
    }


def publish(db: Session, submission: Submission, teacher: User) -> FinalResult:
    if submission.status != S.APPROVED.value:
        raise AppError(409, "Only approved marks can be published. Review and approve this submission first.")
    evaluation = current_evaluation(db, submission.id)
    if evaluation is None or evaluation.review_status != ReviewStatus.APPROVED.value or evaluation.final_total is None:
        raise AppError(409, "This submission has no approved marks to publish")
    exam = submission.exam
    db.execute(delete(FinalResult).where(FinalResult.submission_id == submission.id))
    result = FinalResult(
        submission_id=submission.id,
        exam_id=exam.id,
        student_id=submission.student_id,
        evaluation_id=evaluation.id,
        total=evaluation.final_total,
        max_marks=evaluation.total_max,
        percentage=percentage(evaluation.final_total, evaluation.total_max),
        snapshot=build_snapshot(exam, evaluation, include_comments=exam.release_teacher_comments),
        published_by_id=teacher.id,
        published_at=utcnow(),
    )
    db.add(result)
    submission.status = S.PUBLISHED.value
    submission.status_message = "Your result has been published."
    return result


def withdraw(db: Session, submission: Submission) -> None:
    if submission.status != S.PUBLISHED.value:
        raise AppError(409, "This result is not published")
    db.execute(delete(FinalResult).where(FinalResult.submission_id == submission.id))
    submission.status = S.APPROVED.value
    submission.status_message = "Marking is complete. Your teacher will release the results."


def _view(submission: Submission, snapshot: dict, *, provisional: bool, total: Decimal, maximum: Decimal,
          published_at=None) -> ResultView:
    exam = submission.exam
    return ResultView(
        submission_id=submission.id,
        submission_code=submission.code,
        exam_id=exam.id,
        exam_title=exam.title,
        course_code=exam.course.code if exam.course else None,
        section_name=exam.section.name if exam.section else None,
        student_name=submission.student.full_name,
        student_number=submission.student_number,
        provisional=provisional,
        total=total,
        max_marks=maximum,
        percentage=percentage(total, maximum),
        published_at=published_at,
        teacher_comment=snapshot.get("teacher_comment"),
        questions=[
            ResultQuestion(
                label=q["label"], text=q["text"], max_marks=q["max_marks"], awarded=q["awarded"],
                answered=q.get("answered", True), feedback=q.get("feedback"),
                missing_concepts=q.get("missing_concepts", []), teacher_comment=q.get("teacher_comment"),
                criteria=[ResultCriterion(**c) for c in q.get("criteria", [])],
            )
            for q in snapshot.get("questions", [])
        ],
    )


def result_view(db: Session, submission: Submission, *, for_student: bool) -> ResultView | None:
    """The released result, the provisional one where allowed, or None."""
    final = db.scalar(select(FinalResult).where(FinalResult.submission_id == submission.id))
    if final is not None:
        return _view(submission, final.snapshot, provisional=False, total=final.total, maximum=final.max_marks,
                     published_at=final.published_at)

    exam = submission.exam
    provisional_allowed = exam.result_release_mode == ResultReleaseMode.PROVISIONAL.value or not for_student
    if not provisional_allowed or submission.status not in PROVISIONAL_STATUSES or not submission.is_latest:
        return None
    evaluation = current_evaluation(db, submission.id)
    if evaluation is None or evaluation.final_total is None:
        return None
    # Provisional results never include teacher comments: the review may still be in progress.
    snapshot = build_snapshot(exam, evaluation, include_comments=False)
    return _view(submission, snapshot, provisional=True, total=evaluation.final_total, maximum=evaluation.total_max)


