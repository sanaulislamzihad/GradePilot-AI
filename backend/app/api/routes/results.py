"""Result publication, student results, analytics and exports."""

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Client, CurrentUser, DbSession, StudentUser, TeacherUser
from app.core.errors import AppError
from app.models.evaluation import Evaluation, FinalResult
from app.models.exam import Exam, Question
from app.models.submission import Submission, SubmissionStatus as S
from app.models.user import UserRole
from app.schemas.results import (
    ExamAnalytics,
    ExamResultRow,
    ExamResults,
    PublishResult,
    ReleaseSettings,
    ResultView,
    StudentResultItem,
)
from app.services import analytics, audit, reports
from app.services import results as svc
from app.services.exam_service import get_owned_exam, leaves

router = APIRouter(tags=["results"])

_LOAD = (
    selectinload(Submission.exam).selectinload(Exam.questions).selectinload(Question.children),
    selectinload(Submission.exam).selectinload(Exam.course),
    selectinload(Submission.exam).selectinload(Exam.section),
    selectinload(Submission.student),
)


def _visible(db: Session, user, submission_id: uuid.UUID) -> Submission:
    submission = db.scalar(select(Submission).where(Submission.id == submission_id).options(*_LOAD))
    if submission is None:
        raise AppError(404, "Result not found")
    owner = (user.role == UserRole.STUDENT and submission.student_id == user.id) or (
        user.role == UserRole.TEACHER and submission.exam.teacher_id == user.id
    )
    if not owner:
        raise AppError(404, "Result not found")
    return submission


def _view_or_404(db: Session, user, submission: Submission) -> ResultView:
    view = svc.result_view(db, submission, for_student=user.role == UserRole.STUDENT)
    if view is None:
        raise AppError(404, "Results for this submission are not available yet")
    return view


def _exam_with_tree(db: Session, teacher, exam_id: uuid.UUID) -> Exam:
    exam = get_owned_exam(db, teacher, exam_id)
    db.refresh(exam)
    return exam


def _rows(db: Session, exam: Exam) -> list[ExamResultRow]:
    submissions = db.scalars(
        select(Submission).where(Submission.exam_id == exam.id, Submission.is_latest.is_(True))
        .options(selectinload(Submission.student)).order_by(Submission.student_number)
    ).all()
    evaluations = {
        e.submission_id: e
        for e in db.scalars(select(Evaluation).where(
            Evaluation.submission_id.in_([s.id for s in submissions]), Evaluation.is_current.is_(True)))
    }
    finals = {f.submission_id: f for f in db.scalars(select(FinalResult).where(FinalResult.exam_id == exam.id))}
    rows = []
    for s in submissions:
        final = finals.get(s.id)
        evaluation = evaluations.get(s.id)
        total = final.total if final else (evaluation.final_total if evaluation else None)
        maximum = final.max_marks if final else exam.total_marks
        rows.append(ExamResultRow(
            submission_id=s.id, submission_code=s.code, student_name=s.student.full_name,
            student_number=s.student_number, status=s.status, final_total=total, max_marks=maximum,
            percentage=svc.percentage(total, maximum) if total is not None else None,
            published=final is not None, published_at=final.published_at if final else None,
        ))
    return rows


# --- Teacher: release settings, publication, overview ----------------------

@router.get("/exams/{exam_id}/results", response_model=ExamResults)
def exam_results(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> ExamResults:
    exam = get_owned_exam(db, teacher, exam_id)
    rows = _rows(db, exam)
    return ExamResults(
        exam_id=exam.id, exam_title=exam.title, result_release_mode=exam.result_release_mode,  # type: ignore[arg-type]
        release_teacher_comments=exam.release_teacher_comments, rows=rows,
        approved_unpublished=sum(1 for r in rows if r.status == S.APPROVED.value),
    )


@router.patch("/exams/{exam_id}/release-settings", response_model=ReleaseSettings)
def update_release_settings(
    exam_id: uuid.UUID, data: ReleaseSettings, teacher: TeacherUser, db: DbSession, client: Client
) -> ReleaseSettings:
    """Allowed at any time, including while the exam is published."""
    exam = get_owned_exam(db, teacher, exam_id)
    exam.result_release_mode = data.result_release_mode.value
    exam.release_teacher_comments = data.release_teacher_comments
    audit.record(db, "exam.release_settings", actor=teacher, entity_type="exam", entity_id=exam.id,
                 details={"title": exam.title, "mode": data.result_release_mode.value,
                          "comments": data.release_teacher_comments}, ip_address=client.ip_address)
    db.commit()
    return data


@router.post("/results/{submission_id}/publish", response_model=ResultView)
def publish_result(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> ResultView:
    submission = _visible(db, teacher, submission_id)
    svc.publish(db, submission, teacher)
    audit.record(db, "result.publish", actor=teacher, entity_type="submission", entity_id=submission.id,
                 details={"code": submission.code}, ip_address=client.ip_address)
    db.commit()
    return _view_or_404(db, teacher, submission)


@router.post("/results/{submission_id}/withdraw", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_result(submission_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> Response:
    submission = _visible(db, teacher, submission_id)
    svc.withdraw(db, submission)
    audit.record(db, "result.withdraw", actor=teacher, entity_type="submission", entity_id=submission.id,
                 details={"code": submission.code}, ip_address=client.ip_address)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/exams/{exam_id}/publish-results", response_model=PublishResult)
def publish_exam_results(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> PublishResult:
    """Publish every approved result of an exam. Submissions still under review are left alone."""
    exam = get_owned_exam(db, teacher, exam_id)
    submissions = db.scalars(
        select(Submission).where(Submission.exam_id == exam.id, Submission.is_latest.is_(True)).options(*_LOAD)
    ).all()
    published = skipped = 0
    for submission in submissions:
        if submission.status == S.APPROVED.value:
            svc.publish(db, submission, teacher)
            published += 1
        elif submission.status != S.PUBLISHED.value:
            skipped += 1
    audit.record(db, "result.publish_all", actor=teacher, entity_type="exam", entity_id=exam.id,
                 details={"title": exam.title, "published": published}, ip_address=client.ip_address)
    db.commit()
    return PublishResult(published=published, skipped=skipped)


# --- Viewing results --------------------------------------------------------

@router.get("/results/{submission_id}", response_model=ResultView)
def get_result(submission_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ResultView:
    return _view_or_404(db, user, _visible(db, user, submission_id))


@router.get("/results/{submission_id}/pdf")
def result_pdf(submission_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    submission = _visible(db, user, submission_id)
    view = _view_or_404(db, user, submission)
    return Response(
        reports.result_pdf(view),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{submission.code}-result.pdf"', "Cache-Control": "private, no-store"},
    )


@router.get("/student/results", response_model=list[StudentResultItem])
def student_results(student: StudentUser, db: DbSession) -> list[StudentResultItem]:
    submissions = db.scalars(
        select(Submission).where(Submission.student_id == student.id, Submission.is_latest.is_(True))
        .options(*_LOAD).order_by(Submission.submitted_at.desc())
    ).all()
    items = []
    for submission in submissions:
        view = svc.result_view(db, submission, for_student=True)
        if view is None:
            continue
        items.append(StudentResultItem(
            submission_id=submission.id, exam_id=view.exam_id, exam_title=view.exam_title, course_code=view.course_code,
            provisional=view.provisional, total=view.total, max_marks=view.max_marks, percentage=view.percentage,
            published_at=view.published_at,
        ))
    return items


# --- Analytics and exports -------------------------------------------------

@router.get("/exams/{exam_id}/analytics", response_model=ExamAnalytics)
def exam_analytics(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> ExamAnalytics:
    return analytics.compute(db, _exam_with_tree(db, teacher, exam_id))


def _filename(exam: Exam, suffix: str) -> str:
    base = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in exam.title).strip("-")[:60] or "exam"
    return f"{base}-{suffix}"


@router.get("/exams/{exam_id}/results.csv")
def results_csv(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> Response:
    exam = _exam_with_tree(db, teacher, exam_id)
    gradable = list(leaves(exam))
    finals = {f.submission_id: f for f in db.scalars(select(FinalResult).where(FinalResult.exam_id == exam.id))}
    rows = []
    for row in _rows(db, exam):
        per_question: dict[str, float | None] = {}
        final = finals.get(row.submission_id)
        if final:
            per_question = {q["label"]: q["awarded"] for q in final.snapshot.get("questions", [])}
        rows.append([
            row.student_number, row.student_name, row.submission_code, row.status,
            "" if row.final_total is None else f"{row.final_total:.2f}", f"{row.max_marks:.2f}",
            "" if row.percentage is None else f"{row.percentage:.2f}", "yes" if row.published else "no",
            *["" if per_question.get(label) is None else per_question[label] for _, label in gradable],
        ])
    header = ["Student ID", "Name", "Submission", "Status", "Final marks", "Max marks", "Percentage", "Published",
              *[f"Q{label}" for _, label in gradable]]
    return Response(
        reports.results_csv(header, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_filename(exam, "results.csv")}"', "Cache-Control": "private, no-store"},
    )


@router.get("/exams/{exam_id}/report.pdf")
def class_report(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> Response:
    exam = _exam_with_tree(db, teacher, exam_id)
    stats = analytics.compute(db, exam)
    rows = [r.model_dump() for r in _rows(db, exam)]
    return Response(
        reports.class_report_pdf(stats, rows),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_filename(exam, "report.pdf")}"', "Cache-Control": "private, no-store"},
    )
