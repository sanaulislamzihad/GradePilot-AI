"""Exams, their questions, model answers, rubrics and uploaded documents.

Enumerated values are stored as short strings rather than database enum types
so new values can be added later without a type migration on PostgreSQL.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, Timestamps, UTCDateTime, UUIDPrimaryKey, utcnow
from app.models.course import Course, CourseSection
from app.models.user import User


class ExamType(str, enum.Enum):
    QUIZ = "quiz"
    ASSIGNMENT = "assignment"
    MIDTERM = "midterm"
    FINAL = "final"


class ExamStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ResultReleaseMode(str, enum.Enum):
    # Mode B (default): students see results only after the teacher approves and publishes.
    AFTER_APPROVAL = "after_approval"
    # Mode A: students see AI marks, labelled provisional, as soon as marking finishes.
    PROVISIONAL = "provisional"


class QuestionType(str, enum.Enum):
    SHORT = "short"
    DESCRIPTIVE = "descriptive"
    MATHEMATICAL = "mathematical"
    MULTIPLE_CHOICE = "multiple_choice"


class AnswerSource(str, enum.Enum):
    MANUAL = "manual"
    UPLOADED = "uploaded"
    AI_GENERATED = "ai_generated"


class DocumentKind(str, enum.Enum):
    QUESTION_PAPER = "question_paper"
    MODEL_ANSWER = "model_answer"


class ExtractionStatus(str, enum.Enum):
    SUCCEEDED = "succeeded"
    # Scanned PDF or image: needs OCR / a vision model (Phase 4).
    NEEDS_OCR = "needs_ocr"
    FAILED = "failed"


MARKS = Numeric(7, 2)


class Exam(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "exams"

    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), index=True, nullable=True
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("course_sections.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    exam_type: Mapped[str] = mapped_column(String(20), default=ExamType.QUIZ.value)
    status: Mapped[str] = mapped_column(String(20), default=ExamStatus.DRAFT.value, index=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    submission_deadline: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    total_marks: Mapped[Decimal] = mapped_column(MARKS)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_formats: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["pdf", "jpg", "jpeg", "png"])
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=20)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    result_release_mode: Mapped[str] = mapped_column(
        String(20), default=ResultReleaseMode.AFTER_APPROVAL.value, server_default=ResultReleaseMode.AFTER_APPROVAL.value
    )
    release_teacher_comments: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Unguessable token for the shareable exam link; created on first publish.
    public_slug: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    teacher: Mapped[User] = relationship()
    course: Mapped[Course | None] = relationship()
    section: Mapped[CourseSection | None] = relationship()
    questions: Mapped[list["Question"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", order_by="Question.position"
    )
    documents: Mapped[list["ExamDocument"]] = relationship(back_populates="exam", cascade="all, delete-orphan")


class Question(UUIDPrimaryKey, Timestamps, Base):
    """A question or, when `parent_id` is set, a sub-question.

    Marks live on leaf questions only; a parent's marks are the sum of its children.
    """

    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("exam_id", "parent_id", "label", name="uq_questions_exam_parent_label"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=True
    )
    label: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    question_type: Mapped[str] = mapped_column(String(30), default=QuestionType.DESCRIPTIVE.value)
    marks: Mapped[Decimal | None] = mapped_column(MARKS, nullable=True)

    exam: Mapped[Exam] = relationship(back_populates="questions")
    parent: Mapped["Question | None"] = relationship(remote_side="Question.id", back_populates="children")
    children: Mapped[list["Question"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", order_by="Question.position"
    )
    model_answer: Mapped["ModelAnswer | None"] = relationship(
        back_populates="question", cascade="all, delete-orphan", uselist=False
    )
    rubric: Mapped["Rubric | None"] = relationship(
        back_populates="question", cascade="all, delete-orphan", uselist=False
    )


class ModelAnswer(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "model_answers"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), unique=True
    )
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default=AnswerSource.MANUAL.value)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    question: Mapped[Question] = relationship(back_populates="model_answer")


class Rubric(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "rubrics"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), unique=True
    )
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    question: Mapped[Question] = relationship(back_populates="rubric")
    criteria: Mapped[list["RubricCriterion"]] = relationship(
        back_populates="rubric", cascade="all, delete-orphan", order_by="RubricCriterion.position"
    )


class RubricCriterion(UUIDPrimaryKey, Base):
    __tablename__ = "rubric_criteria"

    rubric_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rubrics.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_marks: Mapped[Decimal] = mapped_column(MARKS)

    rubric: Mapped[Rubric] = relationship(back_populates="criteria")


class ExamDocument(UUIDPrimaryKey, Base):
    """Metadata for an uploaded file. The bytes live in private storage under `storage_key`."""

    __tablename__ = "exam_documents"

    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20))
    extraction_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    exam: Mapped[Exam] = relationship(back_populates="documents")
