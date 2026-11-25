"""Student-only routes: joining and leaving course sections."""

import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import Client, DbSession, StudentUser
from app.core.errors import AppError
from app.models.course import Course, CourseSection, SectionEnrollment
from app.models.user import User
from app.schemas.course import JoinSectionRequest, StudentEnrollment
from app.schemas.submission import StudentExamDetail, StudentExamItem
from app.services import audit
from app.services import submission_service
from app.services.course_service import join_section

router = APIRouter(prefix="/student", tags=["student"])


def to_student_enrollment(enrollment: SectionEnrollment) -> StudentEnrollment:
    section = enrollment.section
    course = section.course
    return StudentEnrollment(
        enrollment_id=enrollment.id,
        section_id=section.id,
        section_name=section.name,
        course_id=course.id,
        course_code=course.code,
        course_name=course.name,
        teacher_name=course.teacher.full_name,
        joined_at=enrollment.joined_at,
    )


def list_student_enrollments(db: Session, student: User) -> list[StudentEnrollment]:
    enrollments = db.scalars(
        select(SectionEnrollment)
        .where(SectionEnrollment.student_id == student.id)
        .options(
            joinedload(SectionEnrollment.section).joinedload(CourseSection.course).joinedload(Course.teacher)
        )
        .order_by(SectionEnrollment.joined_at.desc())
    ).all()
    return [to_student_enrollment(e) for e in enrollments]


@router.get("/enrollments", response_model=list[StudentEnrollment])
def my_enrollments(student: StudentUser, db: DbSession) -> list[StudentEnrollment]:
    return list_student_enrollments(db, student)


@router.post("/enrollments", response_model=StudentEnrollment, status_code=status.HTTP_201_CREATED)
def join(data: JoinSectionRequest, student: StudentUser, db: DbSession, client: Client) -> StudentEnrollment:
    enrollment = join_section(db, student, data.join_code)
    section = enrollment.section
    audit.record(db, "enrollment.join", actor=student, entity_type="section", entity_id=section.id,
                 details={"code": section.course.code, "section": section.name}, ip_address=client.ip_address)
    db.commit()
    return to_student_enrollment(enrollment)


@router.delete("/enrollments/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
def leave(enrollment_id: uuid.UUID, student: StudentUser, db: DbSession, client: Client) -> Response:
    enrollment = db.get(SectionEnrollment, enrollment_id)
    if enrollment is None or enrollment.student_id != student.id:
        raise AppError(404, "Enrollment not found")
    section = enrollment.section
    audit.record(db, "enrollment.leave", actor=student, entity_type="section", entity_id=section.id,
                 details={"code": section.course.code, "section": section.name}, ip_address=client.ip_address)
    db.delete(enrollment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/exams", response_model=list[StudentExamItem])
def available_exams(student: StudentUser, db: DbSession) -> list[StudentExamItem]:
    """Published exams for the student's sections and any exam they have submitted to."""
    return submission_service.available_exams(db, student)


@router.get("/exams/{slug}", response_model=StudentExamDetail)
def exam_for_student(slug: str, student: StudentUser, db: DbSession) -> StudentExamDetail:
    """Any published exam reachable by its link, with this student's eligibility and attempts."""
    exam = submission_service.published_exam_by_slug(db, slug)
    return submission_service.exam_detail(db, exam, student)
