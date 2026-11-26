import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.exam import ExamType
from app.models.submission import SubmissionStatus
from app.schemas.common import ORMModel
from app.schemas.exam import MarksOut


class SubmissionFileRead(ORMModel):
    id: uuid.UUID
    position: int
    original_filename: str
    content_type: str
    size_bytes: int
    page_count: int


class SubmissionStudent(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    student_number: str


class SubmissionSummary(BaseModel):
    id: uuid.UUID
    code: str
    exam_id: uuid.UUID
    exam_title: str
    course_code: str | None
    section_name: str | None
    student: SubmissionStudent
    attempt_number: int
    is_latest: bool
    status: SubmissionStatus
    status_message: str | None
    file_count: int
    page_count: int
    total_size_bytes: int
    submitted_at: datetime


class SubmissionDetail(SubmissionSummary):
    max_attempts: int
    submission_deadline: datetime | None
    files: list[SubmissionFileRead]


class LatestSubmission(BaseModel):
    id: uuid.UUID
    code: str
    status: SubmissionStatus
    attempt_number: int
    submitted_at: datetime


class StudentExamItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    exam_type: ExamType
    course_code: str | None
    course_name: str | None
    section_name: str | None
    teacher_name: str
    total_marks: MarksOut
    submission_deadline: datetime | None
    is_open: bool
    max_attempts: int
    attempts_used: int
    latest_submission: LatestSubmission | None


class StudentExamDetail(StudentExamItem):
    exam_date: date | None
    instructions: str | None
    allowed_formats: list[str]
    max_file_size_mb: int
    question_count: int
    can_submit: bool
    # Why submitting is not possible right now, in words a student can act on.
    blocked_reason: str | None
    attempts_left: int
    submissions: list[SubmissionSummary]
