"""Import every model here so Alembic autogenerate and `Base.metadata` see them."""

from app.models.audit_log import AuditLog
from app.models.course import Course, CourseSection, SectionEnrollment
from app.models.exam import (
    AnswerSource,
    DocumentKind,
    Exam,
    ExamDocument,
    ExamStatus,
    ExamType,
    ExtractionStatus,
    ModelAnswer,
    Question,
    QuestionType,
    Rubric,
    RubricCriterion,
)
from app.models.user import RefreshToken, User, UserRole

__all__ = [
    "AnswerSource",
    "DocumentKind",
    "Exam",
    "ExamDocument",
    "ExamStatus",
    "ExamType",
    "ExtractionStatus",
    "ModelAnswer",
    "Question",
    "QuestionType",
    "Rubric",
    "RubricCriterion",
    "AuditLog",
    "Course",
    "CourseSection",
    "RefreshToken",
    "SectionEnrollment",
    "User",
    "UserRole",
]
