import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.exam import ResultReleaseMode
from app.schemas.exam import MarksOut


class ResultCriterion(BaseModel):
    name: str
    max_marks: float
    awarded: float
    explanation: str | None = None
    missing_concepts: list[str] = []


class ResultQuestion(BaseModel):
    label: str
    text: str
    max_marks: float
    awarded: float | None
    answered: bool
    feedback: str | None
    missing_concepts: list[str]
    teacher_comment: str | None
    criteria: list[ResultCriterion]


class ResultView(BaseModel):
    """What a student may see of their result. Contains no AI or review internals."""

    submission_id: uuid.UUID
    submission_code: str
    exam_id: uuid.UUID
    exam_title: str
    course_code: str | None
    section_name: str | None
    student_name: str
    student_number: str
    provisional: bool
    total: MarksOut
    max_marks: MarksOut
    percentage: MarksOut
    published_at: datetime | None
    teacher_comment: str | None
    questions: list[ResultQuestion]


class StudentResultItem(BaseModel):
    submission_id: uuid.UUID
    exam_id: uuid.UUID
    exam_title: str
    course_code: str | None
    provisional: bool
    total: MarksOut
    max_marks: MarksOut
    percentage: MarksOut
    published_at: datetime | None


class ExamResultRow(BaseModel):
    submission_id: uuid.UUID
    submission_code: str
    student_name: str
    student_number: str
    status: str
    final_total: MarksOut | None
    max_marks: MarksOut
    percentage: MarksOut | None
    published: bool
    published_at: datetime | None


class ExamResults(BaseModel):
    exam_id: uuid.UUID
    exam_title: str
    result_release_mode: ResultReleaseMode
    release_teacher_comments: bool
    rows: list[ExamResultRow]
    approved_unpublished: int


class ReleaseSettings(BaseModel):
    result_release_mode: ResultReleaseMode
    release_teacher_comments: bool


class PublishResult(BaseModel):
    published: int
    skipped: int


class DistributionBucket(BaseModel):
    label: str
    count: int


class QuestionStat(BaseModel):
    label: str
    text: str
    max_marks: float
    average: float | None
    average_percentage: float | None
    answered: int


class ConceptCount(BaseModel):
    concept: str
    count: int  # number of students whose answers missed it


class ExamAnalytics(BaseModel):
    exam_id: uuid.UUID
    exam_title: str
    total_marks: float
    total_students: int
    total_submissions: int
    pending_evaluations: int  # latest submissions without approved marks yet
    approved_results: int
    published_results: int
    # Statistics use teacher-approved marks only (approved or published).
    graded_count: int
    average: float | None
    median: float | None
    highest: float | None
    lowest: float | None
    average_percentage: float | None
    distribution: list[DistributionBucket]
    questions: list[QuestionStat]
    weakest_questions: list[QuestionStat]
    common_missing_concepts: list[ConceptCount]
