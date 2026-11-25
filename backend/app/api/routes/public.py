"""Unauthenticated, read-only exam information behind the shareable link.

Only published exams are visible, and only the details a student needs before
submitting — never questions, model answers or rubrics.
"""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.core.errors import AppError
from app.database.base import as_utc, utcnow
from app.models.exam import Exam, ExamStatus, Question
from app.schemas.exam import PublicExam
from app.services.exam_service import leaves

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/exams/{slug}", response_model=PublicExam)
def public_exam(slug: str, db: DbSession) -> PublicExam:
    exam = db.scalar(
        select(Exam)
        .where(Exam.public_slug == slug[:32], Exam.status == ExamStatus.PUBLISHED.value)
        .options(
            selectinload(Exam.course), selectinload(Exam.section), selectinload(Exam.teacher),
            selectinload(Exam.questions).selectinload(Question.children),
        )
    )
    if exam is None:
        raise AppError(404, "This exam link is not valid or the exam is not available")
    deadline = exam.submission_deadline
    return PublicExam(
        title=exam.title,
        exam_type=exam.exam_type,  # type: ignore[arg-type]
        course_code=exam.course.code if exam.course else None,
        course_name=exam.course.name if exam.course else None,
        section_name=exam.section.name if exam.section else None,
        teacher_name=exam.teacher.full_name,
        total_marks=exam.total_marks,
        exam_date=exam.exam_date,
        submission_deadline=deadline,
        instructions=exam.instructions,
        allowed_formats=exam.allowed_formats,
        max_file_size_mb=exam.max_file_size_mb,
        max_attempts=exam.max_attempts,
        question_count=sum(1 for _ in leaves(exam)),
        is_open=deadline is not None and as_utc(deadline) > utcnow(),
    )
