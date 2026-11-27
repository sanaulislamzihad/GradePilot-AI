"""Student answer-script submissions and their uploaded files."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, Timestamps, UTCDateTime, UUIDPrimaryKey, utcnow
from app.models.exam import Exam
from app.models.user import User


class SubmissionStatus(str, enum.Enum):
    """Full processing lifecycle. Phase 3 creates submissions as `uploaded`;
    the extraction and evaluation pipeline (Phases 4–6) moves them forward."""

    UPLOADED = "uploaded"
    QUEUED = "queued"
    EXTRACTING = "extracting"
    OCR_REVIEW_REQUIRED = "ocr_review_required"
    READY_FOR_EVALUATION = "ready_for_evaluation"
    EVALUATING = "evaluating"
    VERIFYING = "verifying"
    TEACHER_REVIEW_REQUIRED = "teacher_review_required"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"


class Submission(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", "attempt_number", name="uq_submissions_exam_student_attempt"),
        UniqueConstraint("student_id", "idempotency_key", name="uq_submissions_student_idempotency"),
        Index("ix_submissions_exam_status", "exam_id", "status"),
    )

    # Short, human-friendly reference shown to the student, e.g. "GP-K7PM2QXR".
    code: Mapped[str] = mapped_column(String(16), unique=True)
    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Institution student ID as it was when the script was submitted.
    student_number: Mapped[str] = mapped_column(String(40))
    attempt_number: Mapped[int] = mapped_column(Integer)
    # Only the latest attempt is graded; earlier attempts are kept for the record.
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default=SubmissionStatus.UPLOADED.value)
    # Shown to the student and the teacher; always safe for students to read.
    status_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Technical detail of the last processing failure, for the teacher only.
    processing_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Extraction remarks for the teacher, e.g. text that could not be matched to a question.
    extraction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_count: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer)
    total_size_bytes: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    exam: Mapped[Exam] = relationship()
    student: Mapped[User] = relationship()
    files: Mapped[list["SubmissionFile"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan", order_by="SubmissionFile.position"
    )


class SubmissionFile(UUIDPrimaryKey, Base):
    __tablename__ = "submission_files"

    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer, default=1)

    submission: Mapped[Submission] = relationship(back_populates="files")
