"""Submission rules: who may submit, file checks, attempts and duplicate protection."""

import re
import secrets
import uuid
from dataclasses import dataclass

import pymupdf
from fastapi import UploadFile
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.database.base import as_utc, utcnow
from app.models.course import CourseSection, SectionEnrollment
from app.models.exam import Exam, ExamStatus, Question
from app.models.submission import Submission, SubmissionFile, SubmissionStatus
from app.models.user import User
from app.schemas.submission import (
    LatestSubmission,
    StudentExamDetail,
    StudentExamItem,
    SubmissionDetail,
    SubmissionFileRead,
    SubmissionStudent,
    SubmissionSummary,
)
from app.services import audit, storage
from app.services.exam_service import leaves
from app.services.uploads import PDF, ValidatedFile, read_validated

MAX_FILES = 30
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_PDF_PAGES = 100
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9\-]{8,64}$")

_EXAM_LOAD = (
    selectinload(Exam.course),
    selectinload(Exam.section),
    selectinload(Exam.teacher),
    selectinload(Exam.questions).selectinload(Question.children),
)


# --- Access ----------------------------------------------------------------

def published_exam_by_slug(db: Session, slug: str) -> Exam:
    exam = db.scalar(
        select(Exam).where(Exam.public_slug == slug[:32], Exam.status == ExamStatus.PUBLISHED.value).options(*_EXAM_LOAD)
    )
    if exam is None:
        raise AppError(404, "This exam link is not valid or the exam is not available")
    return exam


def is_enrolled(db: Session, exam: Exam, student: User) -> bool:
    """Course-linked exams are for that course's (or section's) students only."""
    if exam.course_id is None:
        return True
    query = (
        select(SectionEnrollment.id)
        .join(CourseSection, SectionEnrollment.section_id == CourseSection.id)
        .where(SectionEnrollment.student_id == student.id)
    )
    if exam.section_id is not None:
        query = query.where(SectionEnrollment.section_id == exam.section_id)
    else:
        query = query.where(CourseSection.course_id == exam.course_id)
    return db.scalar(query) is not None


def is_open(exam: Exam) -> bool:
    return exam.submission_deadline is not None and as_utc(exam.submission_deadline) > utcnow()


def student_attempts(db: Session, exam: Exam, student: User) -> list[Submission]:
    return list(
        db.scalars(
            select(Submission)
            .where(Submission.exam_id == exam.id, Submission.student_id == student.id)
            .options(selectinload(Submission.exam).selectinload(Exam.course), selectinload(Submission.student))
            .order_by(Submission.attempt_number.desc())
        )
    )


def submission_block(db: Session, exam: Exam, student: User, attempts_used: int) -> tuple[int, str] | None:
    """Why this student cannot submit right now, as (HTTP status, message), or None."""
    if exam.status != ExamStatus.PUBLISHED.value:
        return 409, "This exam is not open for submissions."
    if not is_enrolled(db, exam, student):
        target = exam.course.code if exam.course else "this course"
        if exam.section:
            target += f" Section {exam.section.name}"
        return 403, f"This exam is for students of {target}. Join the section with the code from your teacher first."
    if not is_open(exam):
        return 409, "The submission deadline has passed."
    if attempts_used >= exam.max_attempts:
        if exam.max_attempts == 1:
            return 409, "You have already submitted this exam."
        return 409, f"You have used all {exam.max_attempts} submission attempts."
    return None


def blocked_reason(db: Session, exam: Exam, student: User, attempts_used: int) -> str | None:
    block = submission_block(db, exam, student, attempts_used)
    return block[1] if block else None


# --- Serialisation ---------------------------------------------------------

def summary(submission: Submission) -> SubmissionSummary:
    exam = submission.exam
    return SubmissionSummary(
        id=submission.id,
        code=submission.code,
        exam_id=exam.id,
        exam_title=exam.title,
        course_code=exam.course.code if exam.course else None,
        section_name=exam.section.name if exam.section else None,
        student=SubmissionStudent(
            id=submission.student.id,
            full_name=submission.student.full_name,
            email=submission.student.email,
            student_number=submission.student_number,
        ),
        attempt_number=submission.attempt_number,
        is_latest=submission.is_latest,
        status=submission.status,  # type: ignore[arg-type]
        status_message=submission.status_message,
        file_count=submission.file_count,
        page_count=submission.page_count,
        total_size_bytes=submission.total_size_bytes,
        submitted_at=submission.submitted_at,
    )


def detail(submission: Submission) -> SubmissionDetail:
    return SubmissionDetail(
        **summary(submission).model_dump(),
        max_attempts=submission.exam.max_attempts,
        submission_deadline=submission.exam.submission_deadline,
        files=[SubmissionFileRead.model_validate(f) for f in submission.files],
    )


def _latest(attempts: list[Submission]) -> LatestSubmission | None:
    latest = next((s for s in attempts if s.is_latest), None)
    if latest is None:
        return None
    return LatestSubmission(
        id=latest.id, code=latest.code, status=latest.status,  # type: ignore[arg-type]
        attempt_number=latest.attempt_number, submitted_at=latest.submitted_at,
    )


def exam_item(exam: Exam, attempts: list[Submission]) -> StudentExamItem:
    return StudentExamItem(
        id=exam.id,
        slug=exam.public_slug or "",
        title=exam.title,
        exam_type=exam.exam_type,  # type: ignore[arg-type]
        course_code=exam.course.code if exam.course else None,
        course_name=exam.course.name if exam.course else None,
        section_name=exam.section.name if exam.section else None,
        teacher_name=exam.teacher.full_name,
        total_marks=exam.total_marks,
        submission_deadline=exam.submission_deadline,
        is_open=is_open(exam),
        max_attempts=exam.max_attempts,
        attempts_used=len(attempts),
        latest_submission=_latest(attempts),
    )


def exam_detail(db: Session, exam: Exam, student: User) -> StudentExamDetail:
    attempts = student_attempts(db, exam, student)
    reason = blocked_reason(db, exam, student, len(attempts))
    return StudentExamDetail(
        **exam_item(exam, attempts).model_dump(),
        exam_date=exam.exam_date,
        instructions=exam.instructions,
        allowed_formats=exam.allowed_formats,
        max_file_size_mb=exam.max_file_size_mb,
        question_count=sum(1 for _ in leaves(exam)),
        can_submit=reason is None,
        blocked_reason=reason,
        attempts_left=max(0, exam.max_attempts - len(attempts)),
        submissions=[summary(s) for s in attempts],
    )


def available_exams(db: Session, student: User) -> list[StudentExamItem]:
    """Published exams for the student's sections, plus any exam they have submitted to."""
    section_ids = select(SectionEnrollment.section_id).where(SectionEnrollment.student_id == student.id)
    course_ids = select(CourseSection.course_id).where(CourseSection.id.in_(section_ids))
    submitted_exam_ids = select(Submission.exam_id).where(Submission.student_id == student.id)

    exams = db.scalars(
        select(Exam)
        .where(
            Exam.status == ExamStatus.PUBLISHED.value,
            or_(
                Exam.section_id.in_(section_ids),
                and_(Exam.section_id.is_(None), Exam.course_id.in_(course_ids)),
                Exam.id.in_(submitted_exam_ids),
            ),
        )
        .options(*_EXAM_LOAD)
    ).all()

    attempts_by_exam: dict[uuid.UUID, list[Submission]] = {}
    for submission in db.scalars(
        select(Submission).where(Submission.student_id == student.id).order_by(Submission.attempt_number.desc())
    ):
        attempts_by_exam.setdefault(submission.exam_id, []).append(submission)

    items = [exam_item(e, attempts_by_exam.get(e.id, [])) for e in exams]
    # Open exams first, soonest deadline first; closed ones after.
    items.sort(key=lambda i: (not i.is_open, i.submission_deadline or utcnow()))
    return items


# --- Creating a submission -------------------------------------------------

@dataclass
class _PreparedFile:
    validated: ValidatedFile
    page_count: int


def _pdf_pages(data: bytes) -> int:
    try:
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if document.needs_pass:
                raise AppError(400, "The PDF is password-protected. Upload an unlocked copy.")
            pages = document.page_count
    except AppError:
        raise
    except Exception:  # noqa: BLE001 - PyMuPDF raises several types for damaged files
        raise AppError(400, "The PDF is damaged or could not be opened") from None
    if pages == 0:
        raise AppError(400, "The PDF has no pages")
    if pages > MAX_PDF_PAGES:
        raise AppError(413, f"The PDF has more than {MAX_PDF_PAGES} pages")
    return pages


async def _prepare_files(exam: Exam, uploads: list[UploadFile]) -> list[_PreparedFile]:
    if not uploads:
        raise AppError(422, "Attach your answer script")
    if len(uploads) > MAX_FILES:
        raise AppError(422, f"Upload at most {MAX_FILES} files")

    allowed = set(exam.allowed_formats)
    prepared: list[_PreparedFile] = []
    total = 0
    for upload in uploads:
        validated = await read_validated(upload, allowed, exam.max_file_size_mb * 1024 * 1024)
        total += len(validated.data)
        if total > MAX_TOTAL_BYTES:
            raise AppError(413, f"The files together exceed {MAX_TOTAL_BYTES // (1024 * 1024)} MB")
        pages = _pdf_pages(validated.data) if validated.kind == PDF else 1
        prepared.append(_PreparedFile(validated, pages))

    if any(p.validated.kind == PDF for p in prepared) and len(prepared) > 1:
        raise AppError(422, "Upload your script as one PDF, or as one image per page — not both or several PDFs")
    return prepared


def _generate_code(db: Session) -> str:
    for _ in range(20):
        code = "GP-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        if not db.scalar(select(Submission.id).where(Submission.code == code)):
            return code
    raise AppError(500, "Could not create a submission reference. Please try again.")


def find_by_idempotency_key(db: Session, student: User, key: str | None) -> Submission | None:
    if not key:
        return None
    return db.scalar(select(Submission).where(Submission.student_id == student.id, Submission.idempotency_key == key))


def validate_idempotency_key(key: str | None) -> str | None:
    if key is None:
        return None
    if not _IDEMPOTENCY_KEY.match(key):
        raise AppError(422, "Invalid Idempotency-Key header")
    return key


async def create_submission(
    db: Session, exam: Exam, student: User, uploads: list[UploadFile], idempotency_key: str | None, ip: str | None
) -> tuple[Submission, bool]:
    """Return (submission, created). A repeated request with the same key returns the original."""
    existing = find_by_idempotency_key(db, student, idempotency_key)
    if existing is not None:
        return existing, False

    attempts = student_attempts(db, exam, student)
    block = submission_block(db, exam, student, len(attempts))
    if block:
        raise AppError(*block)
    if not student.student_id:
        raise AppError(422, "Your profile has no student ID")

    prepared = await _prepare_files(exam, uploads)

    latest = next((s for s in attempts if s.is_latest), None)
    if latest is not None:
        previous_hashes = [f.sha256 for f in latest.files]
        if previous_hashes == [p.validated.sha256 for p in prepared]:
            raise AppError(409, "These are the same files as your current submission. Nothing was changed.")

    submission_id = uuid.uuid4()
    saved_keys: list[str] = []
    try:
        files = []
        for position, item in enumerate(prepared, start=1):
            key = storage.save(f"submissions/{exam.id}/{submission_id}", item.validated.extension, item.validated.data)
            saved_keys.append(key)
            files.append(SubmissionFile(
                position=position,
                original_filename=item.validated.original_filename,
                storage_key=key,
                content_type=item.validated.kind.content_type,
                size_bytes=len(item.validated.data),
                sha256=item.validated.sha256,
                page_count=item.page_count,
            ))

        if latest is not None:
            latest.is_latest = False
        submission = Submission(
            id=submission_id,
            code=_generate_code(db),
            exam_id=exam.id,
            student_id=student.id,
            student_number=student.student_id,
            attempt_number=len(attempts) + 1,
            is_latest=True,
            status=SubmissionStatus.UPLOADED.value,
            status_message="Received. Automatic evaluation starts once AI evaluation is set up for this exam.",
            file_count=len(files),
            page_count=sum(f.page_count for f in files),
            total_size_bytes=sum(f.size_bytes for f in files),
            idempotency_key=idempotency_key,
            files=files,
        )
        db.add(submission)
        audit.record(
            db, "submission.create", actor=student, entity_type="submission", entity_id=submission_id,
            details={"code": submission.code, "title": exam.title, "attempt": submission.attempt_number},
            ip_address=ip,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        for key in saved_keys:
            storage.delete(key)
        # A concurrent request won the race: return it if it was the same request.
        concurrent = find_by_idempotency_key(db, student, idempotency_key)
        if concurrent is not None:
            return concurrent, False
        raise AppError(409, "Another submission for this exam was just received. Refresh the page.") from None
    except Exception:
        db.rollback()
        for key in saved_keys:
            storage.delete(key)
        raise
    return submission, True


def submission_counts(db: Session, exam_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Latest submissions per exam (one per student)."""
    if not exam_ids:
        return {}
    rows = db.execute(
        select(Submission.exam_id, func.count(Submission.id))
        .where(Submission.exam_id.in_(exam_ids), Submission.is_latest.is_(True))
        .group_by(Submission.exam_id)
    ).all()
    return dict(rows)
