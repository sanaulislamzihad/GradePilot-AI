import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole
from app.schemas.course import StudentEnrollment


class ActivityItem(BaseModel):
    id: uuid.UUID
    action: str
    summary: str
    created_at: datetime


class TeacherCourseSummary(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    section_count: int
    student_count: int


class TeacherDashboard(BaseModel):
    course_count: int
    section_count: int
    student_count: int
    courses: list[TeacherCourseSummary]
    recent_activity: list[ActivityItem]


class StudentDashboard(BaseModel):
    enrollment_count: int
    course_count: int
    enrollments: list[StudentEnrollment]
    recent_activity: list[ActivityItem]


class AdminOverview(BaseModel):
    total_users: int
    active_users: int
    users_by_role: dict[UserRole, int]
    course_count: int
    section_count: int
    enrollment_count: int
    new_users_last_7_days: int


class AuditLogRead(BaseModel):
    id: uuid.UUID
    action: str
    summary: str
    actor_name: str | None
    actor_email: str | None
    entity_type: str | None
    entity_id: str | None
    ip_address: str | None
    created_at: datetime


class SystemStatus(BaseModel):
    status: str
    version: str
    environment: str
    database_backend: str
    database_ok: bool
    migration_revision: str | None
    uptime_seconds: int
    storage_writable: bool
    active_sessions: int
