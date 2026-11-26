"""Extracted answers and AI evaluations of a submission.

Marks are always computed by the backend from validated criterion scores;
a total reported by a model is never stored or trusted.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, Timestamps, UTCDateTime, UUIDPrimaryKey, utcnow
from app.models.exam import Question, RubricCriterion
from app.models.submission import Submission

MARKS = Numeric(7, 2)


class ExtractionSource(str, enum.Enum):
    PDF_TEXT = "pdf_text"  # read from the PDF's text layer
    AI_OCR = "ai_ocr"      # transcribed by the OCR model
    TEACHER = "teacher"    # typed or corrected by the teacher


class AnswerStatus(str, enum.Enum):
    ANSWERED = "answered"
    MISSING = "missing"
    UNREADABLE = "unreadable"


class EvaluationStatus(str, enum.Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractedAnswer(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "extracted_answers"
    __table_args__ = (UniqueConstraint("submission_id", "question_id", name="uq_extracted_answers_submission_question"),)

    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default=AnswerStatus.ANSWERED.value)
    source: Mapped[str] = mapped_column(String(20))
    # 0..1 as reported by the extractor; 1.0 for text-layer PDFs and teacher input.
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    pages: Mapped[list[int]] = mapped_column(JSON, default=list)
    # Parts the extractor could not read, quoted or described, for the teacher to check.
    unreadable_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    submission: Mapped[Submission] = relationship()
    question: Mapped[Question] = relationship()


class Evaluation(UUIDPrimaryKey, Base):
    """One AI grading run over a whole submission."""

    __tablename__ = "evaluations"

    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    run_number: Mapped[int] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(200))
    total_awarded: Mapped[Decimal | None] = mapped_column(MARKS, nullable=True)
    total_max: Mapped[Decimal] = mapped_column(MARKS)
    # Reasons a teacher should look closely, e.g. "evidence_not_found" or "invalid_ai_output".
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    submission: Mapped[Submission] = relationship()
    questions: Mapped[list["EvaluationQuestion"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan", order_by="EvaluationQuestion.position"
    )


class EvaluationQuestion(UUIDPrimaryKey, Base):
    __tablename__ = "evaluation_questions"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluations.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(30))
    answer_status: Mapped[str] = mapped_column(String(20))
    # None when the question could not be graded automatically and needs a teacher.
    awarded: Mapped[Decimal | None] = mapped_column(MARKS, nullable=True)
    max_marks: Mapped[Decimal] = mapped_column(MARKS)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_concepts: Mapped[list[str]] = mapped_column(JSON, default=list)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)

    evaluation: Mapped[Evaluation] = relationship(back_populates="questions")
    criteria: Mapped[list["EvaluationCriterion"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="EvaluationCriterion.position"
    )


class EvaluationCriterion(UUIDPrimaryKey, Base):
    __tablename__ = "evaluation_criteria"

    evaluation_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_questions.id", ondelete="CASCADE"), index=True
    )
    rubric_criterion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rubric_criteria.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    max_marks: Mapped[Decimal] = mapped_column(MARKS)
    awarded: Mapped[Decimal] = mapped_column(MARKS)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_concepts: Mapped[list[str]] = mapped_column(JSON, default=list)

    question: Mapped[EvaluationQuestion] = relationship(back_populates="criteria")
    rubric_criterion: Mapped[RubricCriterion | None] = relationship()
    evidence: Mapped[list["EvaluationEvidence"]] = relationship(
        back_populates="criterion", cascade="all, delete-orphan"
    )


class EvaluationEvidence(UUIDPrimaryKey, Base):
    __tablename__ = "evaluation_evidence"

    evaluation_criterion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_criteria.id", ondelete="CASCADE"), index=True
    )
    quote: Mapped[str] = mapped_column(Text)
    # Whether the quote was actually found in the student's extracted answer.
    found_in_answer: Mapped[bool] = mapped_column(Boolean)

    criterion: Mapped[EvaluationCriterion] = relationship(back_populates="evidence")
