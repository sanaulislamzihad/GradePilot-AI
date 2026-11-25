"""Role dashboards built from live database counts."""

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, StudentUser, TeacherUser
from app.api.routes.student import list_student_enrollments
from app.models.audit_log import AuditLog
from app.models.course import Course, CourseSection, SectionEnrollment
from app.models.exam import Exam, ExamStatus
from app.models.user import User
from app.schemas.dashboard import (
    ActivityItem,
    StudentDashboard,
    TeacherCourseSummary,
    TeacherDashboard,
    TeacherExamSummary,
)
from app.services import audit
from app.services.course_service import course_counts

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_HIDDEN_FROM_ACTIVITY = ("auth.login_failed", "auth.refresh_reuse")


def recent_activity(db: Session, user: User, limit: int = 8) -> list[ActivityItem]:
    entries = db.scalars(
        select(AuditLog)
        .where(AuditLog.actor_id == user.id, AuditLog.action.not_in(_HIDDEN_FROM_ACTIVITY))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        ActivityItem(id=e.id, action=e.action, summary=audit.describe(e), created_at=e.created_at)
        for e in entries
    ]


@router.get("/teacher", response_model=TeacherDashboard)
def teacher_dashboard(teacher: TeacherUser, db: DbSession) -> TeacherDashboard:
    courses = db.scalars(
        select(Course).where(Course.teacher_id == teacher.id).order_by(Course.created_at.desc())
    ).all()
    counts = course_counts(db, [c.id for c in courses])

    section_count = sum(sections for sections, _ in counts.values())
    # Distinct across all courses: a student in two of this teacher's courses counts once.
    student_count = db.scalar(
        select(func.count(func.distinct(SectionEnrollment.student_id)))
        .join(CourseSection, SectionEnrollment.section_id == CourseSection.id)
        .join(Course, CourseSection.course_id == Course.id)
        .where(Course.teacher_id == teacher.id)
    ) or 0

    exam_status_counts = dict(
        db.execute(
            select(Exam.status, func.count(Exam.id)).where(Exam.teacher_id == teacher.id).group_by(Exam.status)
        ).all()
    )
    recent_exams = db.scalars(
        select(Exam).where(Exam.teacher_id == teacher.id).order_by(Exam.updated_at.desc()).limit(5)
    ).all()

    return TeacherDashboard(
        course_count=len(courses),
        section_count=section_count,
        student_count=student_count,
        exam_count=sum(exam_status_counts.values()),
        published_exam_count=exam_status_counts.get(ExamStatus.PUBLISHED.value, 0),
        draft_exam_count=exam_status_counts.get(ExamStatus.DRAFT.value, 0),
        recent_exams=[
            TeacherExamSummary(
                id=e.id, title=e.title, status=e.status,
                course_code=e.course.code if e.course else None,
                submission_deadline=e.submission_deadline,
            )
            for e in recent_exams
        ],
        courses=[
            TeacherCourseSummary(
                id=c.id,
                code=c.code,
                name=c.name,
                section_count=counts.get(c.id, (0, 0))[0],
                student_count=counts.get(c.id, (0, 0))[1],
            )
            for c in courses[:6]
        ],
        recent_activity=recent_activity(db, teacher),
    )


@router.get("/student", response_model=StudentDashboard)
def student_dashboard(student: StudentUser, db: DbSession) -> StudentDashboard:
    enrollments = list_student_enrollments(db, student)
    return StudentDashboard(
        enrollment_count=len(enrollments),
        course_count=len({e.course_id for e in enrollments}),
        enrollments=enrollments,
        recent_activity=recent_activity(db, student),
    )
