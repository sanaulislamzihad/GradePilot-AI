"""Exam rules: ownership, edit locking, question tree, marks and publish readiness."""

import secrets
import string
import uuid
from collections.abc import Iterator
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.database.base import as_utc, utcnow
from app.models.course import Course, CourseSection
from app.models.exam import Exam, ExamDocument, ExamStatus, ModelAnswer, Question, Rubric
from app.models.submission import Submission
from app.models.user import User
from app.schemas.exam import (
    CriterionRead,
    DocumentRead,
    ExamDetail,
    ExamSummary,
    ModelAnswerRead,
    QuestionRead,
    Readiness,
    ReadinessCheck,
    RubricRead,
)
from app.services.question_parser import full_label

ZERO = Decimal("0")

_EXAM_LOAD = (
    selectinload(Exam.questions).selectinload(Question.model_answer),
    selectinload(Exam.questions).selectinload(Question.rubric).selectinload(Rubric.criteria),
    selectinload(Exam.questions).selectinload(Question.children),
    selectinload(Exam.documents),
    selectinload(Exam.course),
    selectinload(Exam.section),
)


# --- Loading and ownership -------------------------------------------------

def get_owned_exam(db: Session, teacher: User, exam_id: uuid.UUID, *, full: bool = False) -> Exam:
    query = select(Exam).where(Exam.id == exam_id)
    if full:
        query = query.options(*_EXAM_LOAD)
    exam = db.scalar(query)
    if exam is None or exam.teacher_id != teacher.id:
        raise AppError(404, "Exam not found")
    return exam


def get_owned_question(db: Session, teacher: User, question_id: uuid.UUID) -> Question:
    question = db.get(Question, question_id)
    if question is None or question.exam.teacher_id != teacher.id:
        raise AppError(404, "Question not found")
    return question


def ensure_editable(exam: Exam) -> None:
    if exam.status == ExamStatus.PUBLISHED.value:
        raise AppError(409, "This exam is published. Unpublish it to make changes.")


def resolve_course_and_section(
    db: Session, teacher: User, course_id: uuid.UUID | None, section_id: uuid.UUID | None
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    if section_id and not course_id:
        raise AppError(422, "Choose a course before choosing a section")
    if course_id:
        course = db.get(Course, course_id)
        if course is None or course.teacher_id != teacher.id:
            raise AppError(422, "Course not found")
    if section_id:
        section = db.get(CourseSection, section_id)
        if section is None or section.course_id != course_id:
            raise AppError(422, "The section does not belong to the selected course")
    return course_id, section_id


# --- Question tree ---------------------------------------------------------

def top_level(exam: Exam) -> list[Question]:
    return sorted((q for q in exam.questions if q.parent_id is None), key=lambda q: q.position)


def leaves(exam: Exam) -> Iterator[tuple[Question, str]]:
    """Yield each gradable question with its display label, in paper order."""
    for question in top_level(exam):
        if question.children:
            for child in sorted(question.children, key=lambda c: c.position):
                yield child, full_label(question.label, child.label)
        else:
            yield question, question.label


def question_marks(question: Question) -> Decimal | None:
    if question.children:
        values = [c.marks for c in question.children if c.marks is not None]
        return sum(values, ZERO) if values else None
    return question.marks


def rubric_total(rubric: Rubric) -> Decimal:
    return sum((c.max_marks for c in rubric.criteria), ZERO)


def sibling_filter(parent_id: uuid.UUID | None):
    return Question.parent_id == parent_id if parent_id else Question.parent_id.is_(None)


def fmt(value: Decimal) -> str:
    """5.00 -> "5", 2.50 -> "2.5"."""
    return f"{value.normalize():f}"


def next_label(db: Session, exam: Exam, parent: Question | None) -> str:
    siblings = db.scalars(
        select(Question.label).where(Question.exam_id == exam.id, sibling_filter(parent.id if parent else None))
    ).all()
    if parent is None:
        numbers = [int(label) for label in siblings if label.isdigit()]
        return str(max(numbers, default=0) + 1)
    for letter in string.ascii_lowercase:
        if letter not in siblings:
            return letter
    return str(len(siblings) + 1)


def ensure_unique_label(
    db: Session, exam: Exam, parent_id: uuid.UUID | None, label: str, exclude_id: uuid.UUID | None = None
) -> None:
    query = select(Question.id).where(
        Question.exam_id == exam.id,
        func.lower(Question.label) == label.lower(),
        sibling_filter(parent_id),
    )
    if exclude_id:
        query = query.where(Question.id != exclude_id)
    if db.scalar(query):
        raise AppError(409, f"Question {label} already exists at this level")


def next_position(db: Session, exam: Exam, parent_id: uuid.UUID | None) -> int:
    current = db.scalar(
        select(func.max(Question.position)).where(
            Question.exam_id == exam.id, sibling_filter(parent_id)
        )
    )
    return (current or 0) + 1


def make_parent(db: Session, question: Question) -> None:
    """A question that gains sub-questions stops being gradable on its own."""
    question.marks = None
    if question.model_answer is not None:
        db.delete(question.model_answer)
    if question.rubric is not None:
        db.delete(question.rubric)


def generate_slug(db: Session) -> str:
    for _ in range(10):
        slug = secrets.token_urlsafe(9)
        if not db.scalar(select(Exam.id).where(Exam.public_slug == slug)):
            return slug
    raise AppError(500, "Could not generate an exam link. Please try again.")


# --- Readiness -------------------------------------------------------------

def readiness(exam: Exam) -> Readiness:
    items = list(leaves(exam))
    allocated = sum((q.marks for q, _ in items if q.marks is not None), ZERO)
    checks: list[ReadinessCheck] = []

    problems = []
    if exam.submission_deadline is None:
        problems.append("set a submission deadline")
    elif as_utc(exam.submission_deadline) <= utcnow():
        problems.append("the submission deadline has passed")
    checks.append(ReadinessCheck(
        key="details", label="Exam details",
        ok=not problems, detail="Complete" if not problems else "Please " + " and ".join(problems),
    ))

    empty = [label for q, label in items if not q.text.strip()]
    checks.append(ReadinessCheck(
        key="questions", label="Questions",
        ok=bool(items) and not empty,
        detail=(
            "Add at least one question" if not items
            else f"Add text to question {', '.join(empty)}" if empty
            else f"{len(items)} gradable question{'s' if len(items) != 1 else ''}"
        ),
    ))

    missing = [label for q, label in items if q.marks is None]
    marks_ok = bool(items) and not missing and allocated == exam.total_marks
    if not items:
        marks_detail = "Add questions first"
    elif missing:
        marks_detail = f"Assign marks to question {', '.join(missing)}"
    elif allocated != exam.total_marks:
        marks_detail = f"Allocated {fmt(allocated)} of {fmt(exam.total_marks)} marks"
    else:
        marks_detail = f"All {fmt(exam.total_marks)} marks allocated"
    checks.append(ReadinessCheck(key="marks", label="Marks", ok=marks_ok, detail=marks_detail))

    approved_answers = [
        label for q, label in items if q.model_answer and q.model_answer.is_approved and q.model_answer.content.strip()
    ]
    checks.append(ReadinessCheck(
        key="model_answers", label="Model answers",
        ok=bool(items) and len(approved_answers) == len(items),
        detail=f"{len(approved_answers)} of {len(items)} approved",
    ))

    rubric_issues = []
    approved_rubrics = 0
    for q, label in items:
        if q.rubric is None or not q.rubric.is_approved:
            continue
        if q.marks is None or rubric_total(q.rubric) != q.marks:
            rubric_issues.append(label)
        else:
            approved_rubrics += 1
    rubric_detail = f"{approved_rubrics} of {len(items)} approved"
    if rubric_issues:
        rubric_detail += f"; rubric total differs from question marks for {', '.join(rubric_issues)}"
    checks.append(ReadinessCheck(
        key="rubrics", label="Marking rubrics",
        ok=bool(items) and approved_rubrics == len(items), detail=rubric_detail,
    ))

    return Readiness(
        ready=all(c.ok for c in checks), allocated_marks=allocated, total_marks=exam.total_marks, checks=checks
    )


# --- Serialisation ---------------------------------------------------------

def _question_read(question: Question, parent_label: str | None) -> QuestionRead:
    rubric = None
    if question.rubric is not None:
        rubric = RubricRead(
            is_approved=question.rubric.is_approved,
            approved_at=question.rubric.approved_at,
            total=rubric_total(question.rubric),
            criteria=[CriterionRead.model_validate(c) for c in question.rubric.criteria],
        )
    return QuestionRead(
        id=question.id,
        parent_id=question.parent_id,
        label=question.label,
        full_label=full_label(parent_label, question.label),
        position=question.position,
        text=question.text,
        question_type=question.question_type,  # type: ignore[arg-type]
        marks=question_marks(question),
        is_leaf=not question.children,
        model_answer=ModelAnswerRead.model_validate(question.model_answer) if question.model_answer else None,
        rubric=rubric,
        children=[
            _question_read(child, question.label)
            for child in sorted(question.children, key=lambda c: c.position)
        ],
    )


def summary(exam: Exam, question_count: int | None = None, submission_count: int = 0) -> ExamSummary:
    return ExamSummary(
        id=exam.id,
        title=exam.title,
        exam_type=exam.exam_type,  # type: ignore[arg-type]
        status=exam.status,  # type: ignore[arg-type]
        course_id=exam.course_id,
        course_code=exam.course.code if exam.course else None,
        course_name=exam.course.name if exam.course else None,
        section_id=exam.section_id,
        section_name=exam.section.name if exam.section else None,
        total_marks=exam.total_marks,
        exam_date=exam.exam_date,
        submission_deadline=exam.submission_deadline,
        question_count=question_count if question_count is not None else sum(1 for _ in leaves(exam)),
        submission_count=submission_count,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        published_at=exam.published_at,
    )


def detail(db: Session, exam_id: uuid.UUID) -> ExamDetail:
    # Always reload so the response reflects every change made in the request.
    db.expire_all()
    exam = db.scalar(select(Exam).where(Exam.id == exam_id).options(*_EXAM_LOAD))
    assert exam is not None
    documents = sorted(exam.documents, key=lambda d: d.created_at, reverse=True)
    submissions = db.scalar(
        select(func.count(Submission.id)).where(Submission.exam_id == exam.id, Submission.is_latest.is_(True))
    ) or 0
    return ExamDetail(
        **summary(exam, submission_count=submissions).model_dump(),
        instructions=exam.instructions,
        allowed_formats=exam.allowed_formats,
        max_file_size_mb=exam.max_file_size_mb,
        max_attempts=exam.max_attempts,
        public_slug=exam.public_slug,
        questions=[_question_read(q, None) for q in top_level(exam)],
        documents=[DocumentRead.model_validate(d) for d in documents],
        readiness=readiness(exam),
    )


def latest_document(exam: Exam, kind: str) -> ExamDocument | None:
    documents = [d for d in exam.documents if d.kind == kind]
    return max(documents, key=lambda d: d.created_at) if documents else None


def set_model_answer(question: Question, content: str, source: str, approved: bool) -> ModelAnswer:
    answer = question.model_answer
    if answer is None:
        answer = ModelAnswer(question_id=question.id, content=content, source=source)
        question.model_answer = answer
    elif answer.content != content:
        answer.content = content
        answer.source = source
    answer.is_approved = approved
    answer.approved_at = utcnow() if approved else None
    return answer
