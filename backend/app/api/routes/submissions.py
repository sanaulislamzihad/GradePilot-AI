"""Answer-script submissions.

Students submit to published exams and see only their own submissions.
Teachers see submissions for their own exams. Anyone else gets a 404, so the
existence of a submission is never revealed.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Header, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Client, CurrentUser, DbSession, StudentUser
from app.core.errors import AppError
from app.models.exam import Exam, ExamStatus
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User, UserRole
from app.schemas.common import Page
from app.schemas.submission import SubmissionDetail, SubmissionSummary
from app.services import storage
from app.services import submission_service as svc

router = APIRouter(tags=["submissions"])

_LOAD = (
    selectinload(Submission.exam).selectinload(Exam.course),
    selectinload(Submission.exam).selectinload(Exam.section),
    selectinload(Submission.student),
    selectinload(Submission.files),
)


def _visible_submission(db: Session, user: User, submission_id: uuid.UUID) -> Submission:
    submission = db.scalar(select(Submission).where(Submission.id == submission_id).options(*_LOAD))
    if submission is None:
        raise AppError(404, "Submission not found")
    allowed = (
        (user.role == UserRole.STUDENT and submission.student_id == user.id)
        or (user.role == UserRole.TEACHER and submission.exam.teacher_id == user.id)
    )
    if not allowed:
        raise AppError(404, "Submission not found")
    return submission


@router.post("/exams/{exam_id}/submissions", response_model=SubmissionDetail, status_code=status.HTTP_201_CREATED)
async def submit_script(
    exam_id: uuid.UUID,
    response: Response,
    student: StudentUser,
    db: DbSession,
    client: Client,
    files: Annotated[list[UploadFile], File(description="One PDF, or one image per page")],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> SubmissionDetail:
    exam = db.get(Exam, exam_id)
    if exam is None or exam.status != ExamStatus.PUBLISHED.value:
        raise AppError(404, "Exam not found")
    key = svc.validate_idempotency_key(idempotency_key)
    submission, created = await svc.create_submission(db, exam, student, files, key, client.ip_address)
    if not created:
        # Same request repeated (double click, retry after a dropped connection).
        response.status_code = status.HTTP_200_OK
    return svc.detail(_visible_submission(db, student, submission.id))


@router.get("/submissions", response_model=Page[SubmissionSummary])
def list_submissions(
    user: CurrentUser,
    db: DbSession,
    exam_id: uuid.UUID | None = None,
    status_filter: Annotated[SubmissionStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    latest_only: bool = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[SubmissionSummary]:
    query = select(Submission).join(Exam, Submission.exam_id == Exam.id)
    if user.role == UserRole.TEACHER:
        query = query.where(Exam.teacher_id == user.id)
    elif user.role == UserRole.STUDENT:
        query = query.where(Submission.student_id == user.id)
    else:
        raise AppError(403, "You do not have permission to perform this action")

    if exam_id:
        query = query.where(Submission.exam_id == exam_id)
    if status_filter:
        query = query.where(Submission.status == status_filter.value)
    if latest_only:
        query = query.where(Submission.is_latest.is_(True))
    if q and q.strip() and user.role == UserRole.TEACHER:
        term = f"%{q.strip()}%"
        query = query.join(User, Submission.student_id == User.id).where(
            or_(User.full_name.ilike(term), Submission.student_number.ilike(term), Submission.code.ilike(term))
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    submissions = db.scalars(
        query.options(*_LOAD).order_by(Submission.submitted_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(items=[svc.summary(s) for s in submissions], total=total, page=page, page_size=page_size)


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: uuid.UUID, user: CurrentUser, db: DbSession) -> SubmissionDetail:
    return svc.detail(_visible_submission(db, user, submission_id))


@router.get("/submissions/{submission_id}/files/{file_id}")
def download_submission_file(
    submission_id: uuid.UUID, file_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> FileResponse:
    submission = _visible_submission(db, user, submission_id)
    file = next((f for f in submission.files if f.id == file_id), None)
    if file is None:
        raise AppError(404, "File not found")
    try:
        path = storage.path_for(file.storage_key)
    except (FileNotFoundError, ValueError):
        raise AppError(404, "The stored file is missing") from None
    return FileResponse(
        path,
        media_type=file.content_type,
        filename=f"{submission.code}-{file.position}{path.suffix}",
        headers={"Cache-Control": "private, no-store"},
    )
