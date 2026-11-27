import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, PlainSerializer, StringConstraints, field_validator

from app.models.exam import AnswerSource, DocumentKind, ExamStatus, ExamType, ExtractionStatus, QuestionType, ResultReleaseMode
from app.schemas.common import ORMModel


def _two_decimals(value: Decimal) -> Decimal:
    if value.as_tuple().exponent < -2:  # type: ignore[operator]
        raise ValueError("Use at most two decimal places")
    return value


# Marks are exact decimals internally and plain numbers in JSON.
Marks = Annotated[
    Decimal,
    Field(gt=0, le=1000),
    AfterValidator(_two_decimals),
    PlainSerializer(lambda v: float(v), return_type=float),
]
MarksOut = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float)]

SUBMISSION_FORMATS = {"pdf", "jpg", "jpeg", "png"}


class ExamBase(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    exam_type: ExamType = ExamType.QUIZ
    course_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    exam_date: date | None = None
    submission_deadline: datetime | None = None
    total_marks: Marks
    instructions: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=5000)] = None
    allowed_formats: list[str] = Field(default_factory=lambda: ["pdf", "jpg", "jpeg", "png"])
    max_file_size_mb: int = Field(default=20, ge=1, le=50)
    max_attempts: int = Field(default=1, ge=1, le=10)

    @field_validator("allowed_formats")
    @classmethod
    def _formats(cls, value: list[str]) -> list[str]:
        formats = {fmt.strip().lower().lstrip(".") for fmt in value}
        if not formats:
            raise ValueError("Allow at least one file format")
        unknown = formats - SUBMISSION_FORMATS
        if unknown:
            raise ValueError(f"Unsupported format: {', '.join(sorted(unknown))}")
        # JPG and JPEG are the same format; allowing one allows both.
        if formats & {"jpg", "jpeg"}:
            formats |= {"jpg", "jpeg"}
        return sorted(formats)

    @field_validator("submission_deadline")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Deadline must include a timezone")
        return value

    @field_validator("instructions", mode="before")
    @classmethod
    def _blank(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


class ExamCreate(ExamBase):
    pass


class ExamUpdate(ExamBase):
    pass


class ExamSummary(BaseModel):
    id: uuid.UUID
    title: str
    exam_type: ExamType
    status: ExamStatus
    course_id: uuid.UUID | None
    course_code: str | None
    course_name: str | None
    section_id: uuid.UUID | None
    section_name: str | None
    total_marks: MarksOut
    exam_date: date | None
    submission_deadline: datetime | None
    question_count: int
    submission_count: int = 0
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


class ModelAnswerRead(ORMModel):
    content: str
    source: AnswerSource
    is_approved: bool
    approved_at: datetime | None
    updated_at: datetime


class CriterionRead(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    max_marks: MarksOut


class RubricRead(BaseModel):
    is_approved: bool
    approved_at: datetime | None
    total: MarksOut
    criteria: list[CriterionRead]


class QuestionRead(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    label: str
    full_label: str
    position: int
    text: str
    question_type: QuestionType
    # Leaf questions carry their own marks; parents report the sum of their children.
    marks: MarksOut | None
    is_leaf: bool
    model_answer: ModelAnswerRead | None
    rubric: RubricRead | None
    children: list["QuestionRead"]


class DocumentRead(ORMModel):
    id: uuid.UUID
    kind: DocumentKind
    original_filename: str
    content_type: str
    size_bytes: int
    page_count: int | None
    extraction_status: ExtractionStatus
    extraction_message: str | None
    extracted_text: str | None
    created_at: datetime


class ReadinessCheck(BaseModel):
    key: str
    label: str
    ok: bool
    detail: str


class Readiness(BaseModel):
    ready: bool
    allocated_marks: MarksOut
    total_marks: MarksOut
    checks: list[ReadinessCheck]


class ExamDetail(ExamSummary):
    result_release_mode: ResultReleaseMode
    release_teacher_comments: bool
    instructions: str | None
    allowed_formats: list[str]
    max_file_size_mb: int
    max_attempts: int
    public_slug: str | None
    questions: list[QuestionRead]
    documents: list[DocumentRead]
    readiness: Readiness


QuestionLabel = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$")
]
QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)]


class QuestionCreate(BaseModel):
    parent_id: uuid.UUID | None = None
    label: QuestionLabel | None = None
    text: QuestionText = ""
    question_type: QuestionType = QuestionType.DESCRIPTIVE
    marks: Marks | None = None


class QuestionUpdate(BaseModel):
    label: QuestionLabel | None = None
    text: QuestionText | None = None
    question_type: QuestionType | None = None
    marks: Marks | None = None
    clear_marks: bool = False


class ReorderRequest(BaseModel):
    parent_id: uuid.UUID | None = None
    ordered_ids: list[uuid.UUID] = Field(min_length=1)


class MarkItem(BaseModel):
    question_id: uuid.UUID
    marks: Marks | None


class MarksUpdate(BaseModel):
    items: list[MarkItem] = Field(min_length=1)


class ExtractQuestionsRequest(BaseModel):
    replace: bool = False


class ExtractQuestionsResult(BaseModel):
    created: int
    with_marks: int
    exam: ExamDetail


class ModelAnswerUpdate(BaseModel):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]
    approved: bool = False


class ModelAnswerUploadResult(BaseModel):
    document: DocumentRead
    matched: list[str]
    skipped_approved: list[str]
    unmatched_questions: list[str]
    unused_sections: list[str]
    exam: ExamDetail


class CriterionInput(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=2000)] = None
    max_marks: Marks


class RubricUpdate(BaseModel):
    criteria: list[CriterionInput] = Field(min_length=1, max_length=30)
    approved: bool = False


class PublicExam(BaseModel):
    title: str
    exam_type: ExamType
    course_code: str | None
    course_name: str | None
    section_name: str | None
    teacher_name: str
    total_marks: MarksOut
    exam_date: date | None
    submission_deadline: datetime | None
    instructions: str | None
    allowed_formats: list[str]
    max_file_size_mb: int
    max_attempts: int
    question_count: int
    is_open: bool
