import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.evaluation import AnswerStatus, EvaluationStatus, ExtractionSource
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
    name: str
    max_marks: MarksOut
    awarded: MarksOut
    explanation: str | None
    missing_concepts: list[str]
    evidence: list[EvidenceRead]


class EvaluationQuestionRead(BaseModel):
    question_id: uuid.UUID
    label: str
    answer_status: AnswerStatus
    awarded: MarksOut | None
    max_marks: MarksOut
    feedback: str | None
    missing_concepts: list[str]
    flags: list[str]
    answer_text: str | None
    criteria: list[EvaluationCriterionRead]


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
    flags: list[str]
    started_at: datetime
    completed_at: datetime | None
    questions: list[EvaluationQuestionRead]


class ProcessPendingResult(BaseModel):
    queued: int
    skipped: int
