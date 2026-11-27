import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.evaluation import (
    AnswerStatus,
    EvaluationStatus,
    ExtractionSource,
    ReviewStatus,
    VerificationStatus,
    VerifierVerdict,
)
from app.schemas.exam import MarksOut


class ExtractedAnswerRead(BaseModel):
    question_id: uuid.UUID
    label: str
    question_text: str
    max_marks: MarksOut | None
    text: str
    status: AnswerStatus
    source: ExtractionSource
    confidence: float
    pages: list[int]
    unreadable_notes: list[str]
    needs_review: bool


class ExtractedAnswerInput(BaseModel):
    question_id: uuid.UUID
    text: Annotated[str, StringConstraints(max_length=20000)]
    # Mark a question as unanswered (text is ignored) or unreadable (left for manual marking).
    status: AnswerStatus = AnswerStatus.ANSWERED


class ExtractedAnswersUpdate(BaseModel):
    answers: list[ExtractedAnswerInput] = Field(min_length=1)
    # Confirm the extraction so the submission can be marked.
    confirm: bool = False


class ExtractionView(BaseModel):
    status: str
    extraction_notes: str | None
    answers: list[ExtractedAnswerRead]


class EvidenceRead(BaseModel):
    quote: str
    found_in_answer: bool


class EvaluationCriterionRead(BaseModel):
    id: uuid.UUID
    name: str
    max_marks: MarksOut
    awarded: MarksOut
    teacher_awarded: MarksOut | None
    final_awarded: MarksOut
    explanation: str | None
    missing_concepts: list[str]
    evidence: list[EvidenceRead]


class VerificationRead(BaseModel):
    provider: str
    model: str
    same_model_as_evaluator: bool
    verdict: VerifierVerdict
    suggested_awarded: MarksOut | None
    rubric_followed: bool | None
    evidence_supports_marks: bool | None
    missed_valid_concepts: list[str]
    unsupported_assumptions: list[str]
    criterion_notes: list[dict]
    comment: str | None


class EvaluationQuestionRead(BaseModel):
    question_id: uuid.UUID
    label: str
    question_type: str
    answer_status: AnswerStatus
    awarded: MarksOut | None
    teacher_awarded: MarksOut | None
    final_awarded: MarksOut | None
    max_marks: MarksOut
    feedback: str | None
    missing_concepts: list[str]
    flags: list[str]
    similarity: float | None
    math_check: dict | None
    teacher_comment: str | None
    answer_text: str | None
    criteria: list[EvaluationCriterionRead]
    verification: VerificationRead | None


class EvaluationRead(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    run_number: int
    is_current: bool
    status: EvaluationStatus
    provider: str
    model: str
    total_awarded: MarksOut | None
    total_max: MarksOut
    final_total: MarksOut | None
    flags: list[str]
    started_at: datetime
    completed_at: datetime | None
    verification_status: VerificationStatus
    review_status: ReviewStatus
    teacher_comment: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    questions: list[EvaluationQuestionRead]


class ProcessPendingResult(BaseModel):
    queued: int
    skipped: int


class CriterionReview(BaseModel):
    criterion_id: uuid.UUID
    # None clears the teacher's mark, falling back to the AI's.
    teacher_awarded: float | None


class QuestionReview(BaseModel):
    question_id: uuid.UUID
    criteria: list[CriterionReview] = Field(default_factory=list)
    teacher_awarded: float | None = None
    teacher_comment: Annotated[str | None, StringConstraints(max_length=2000)] = None


class ReviewUpdate(BaseModel):
    questions: list[QuestionReview] = Field(default_factory=list)
    teacher_comment: Annotated[str | None, StringConstraints(max_length=4000)] = None


class RejectRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class EvaluationQueueItem(BaseModel):
    evaluation_id: uuid.UUID
    submission_id: uuid.UUID
    submission_code: str
    submission_status: str
    exam_id: uuid.UUID
    exam_title: str
    student_name: str
    student_number: str
    total_awarded: MarksOut | None
    final_total: MarksOut | None
    total_max: MarksOut
    flags: list[str]
    verification_status: VerificationStatus
    review_status: ReviewStatus
    completed_at: datetime | None


class HistoryEntry(BaseModel):
    action: str
    summary: str
    actor_name: str | None
    changes: list[dict]
    created_at: datetime


class BulkApproveResult(BaseModel):
    approved: int
    skipped: int
