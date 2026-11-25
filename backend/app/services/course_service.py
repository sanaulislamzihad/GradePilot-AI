"""Course, section and enrollment rules.

Ownership checks return 404 rather than 403 so a teacher cannot probe for the
existence of another teacher's courses.
"""

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.course import Course, CourseSection, SectionEnrollment
from app.models.user import User

# No 0/O, 1/I/L, so codes can be read aloud or copied from a projector.
_JOIN_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_JOIN_CODE_LENGTH = 8


def generate_join_code(db: Session) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(_JOIN_CODE_LENGTH))
        if not db.scalar(select(CourseSection.id).where(CourseSection.join_code == code)):
            return code
    raise AppError(500, "Could not generate a unique join code. Please try again.")


def get_owned_course(db: Session, teacher: User, course_id: uuid.UUID) -> Course:
    course = db.get(Course, course_id)
    if course is None or course.teacher_id != teacher.id:
        raise AppError(404, "Course not found")
    return course


def get_owned_section(db: Session, teacher: User, section_id: uuid.UUID) -> CourseSection:
    section = db.get(CourseSection, section_id)
    if section is None or section.course.teacher_id != teacher.id:
        raise AppError(404, "Section not found")
    return section


def ensure_unique_code(db: Session, teacher: User, code: str, exclude_id: uuid.UUID | None = None) -> None:
    query = select(Course.id).where(Course.teacher_id == teacher.id, Course.code == code)
    if exclude_id is not None:
        query = query.where(Course.id != exclude_id)
    if db.scalar(query):
        raise AppError(409, f"You already have a course with code {code}")


def ensure_unique_section_name(
    db: Session, course: Course, name: str, exclude_id: uuid.UUID | None = None
) -> None:
    query = select(CourseSection.id).where(
        CourseSection.course_id == course.id, func.lower(CourseSection.name) == name.lower()
    )
    if exclude_id is not None:
        query = query.where(CourseSection.id != exclude_id)
    if db.scalar(query):
        raise AppError(409, f"Section {name} already exists in this course")


def section_student_counts(db: Session, section_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not section_ids:
        return {}
    rows = db.execute(
        select(SectionEnrollment.section_id, func.count(SectionEnrollment.id))
        .where(SectionEnrollment.section_id.in_(section_ids))
        .group_by(SectionEnrollment.section_id)
    ).all()
    return {section_id: count for section_id, count in rows}


def course_counts(db: Session, course_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    """Return {course_id: (section_count, distinct_student_count)}."""
    if not course_ids:
        return {}
    rows = db.execute(
        select(
            CourseSection.course_id,
            func.count(func.distinct(CourseSection.id)),
            func.count(func.distinct(SectionEnrollment.student_id)),
        )
        .outerjoin(SectionEnrollment, SectionEnrollment.section_id == CourseSection.id)
        .where(CourseSection.course_id.in_(course_ids))
        .group_by(CourseSection.course_id)
    ).all()
    return {course_id: (sections, students) for course_id, sections, students in rows}


def join_section(db: Session, student: User, join_code: str) -> SectionEnrollment:
    section = db.scalar(select(CourseSection).where(CourseSection.join_code == join_code))
    if section is None:
        raise AppError(404, "No section matches this join code. Check the code with your teacher.")
    if not section.is_open:
        raise AppError(409, "This section is not accepting new students")

    existing = db.scalar(
        select(SectionEnrollment)
        .join(CourseSection, SectionEnrollment.section_id == CourseSection.id)
        .where(SectionEnrollment.student_id == student.id, CourseSection.course_id == section.course_id)
    )
    if existing is not None:
        if existing.section_id == section.id:
            raise AppError(409, "You are already enrolled in this section")
        raise AppError(409, f"You are already enrolled in section {existing.section.name} of this course")

    enrollment = SectionEnrollment(section_id=section.id, student_id=student.id)
    db.add(enrollment)
    db.flush()
    return enrollment
