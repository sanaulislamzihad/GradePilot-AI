"""Teacher-only course and section management."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import Client, DbSession, TeacherUser
from app.core.errors import AppError
from app.models.course import Course, CourseSection, SectionEnrollment
from app.models.user import User
from app.schemas.common import Page
from app.schemas.course import (
    CourseCreate,
    CourseDetail,
    CourseRead,
    CourseUpdate,
    EnrolledStudent,
    SectionCreate,
    SectionRead,
    SectionUpdate,
)
from app.services import audit
from app.services import course_service as svc

router = APIRouter(tags=["courses"])


def _course_read(course: Course, counts: dict[uuid.UUID, tuple[int, int]]) -> CourseRead:
    sections, students = counts.get(course.id, (0, 0))
    return CourseRead.model_validate(course).model_copy(
        update={"section_count": sections, "student_count": students}
    )


def _section_read(section: CourseSection, counts: dict[uuid.UUID, int]) -> SectionRead:
    return SectionRead.model_validate(section).model_copy(update={"student_count": counts.get(section.id, 0)})


def _course_detail(db: DbSession, course: Course) -> CourseDetail:
    db.refresh(course, ["sections"])
    section_counts = svc.section_student_counts(db, [s.id for s in course.sections])
    base = _course_read(course, svc.course_counts(db, [course.id]))
    return CourseDetail(
        **base.model_dump(), sections=[_section_read(s, section_counts) for s in course.sections]
    )


def _section_details(section: CourseSection) -> dict:
    return {"code": section.course.code, "section": section.name}


@router.get("/courses", response_model=Page[CourseRead])
def list_courses(
    teacher: TeacherUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[CourseRead]:
    query = select(Course).where(Course.teacher_id == teacher.id)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(Course.code.ilike(term), Course.name.ilike(term)))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    courses = db.scalars(
        query.order_by(Course.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    counts = svc.course_counts(db, [c.id for c in courses])
    return Page(items=[_course_read(c, counts) for c in courses], total=total, page=page, page_size=page_size)


@router.post("/courses", response_model=CourseDetail, status_code=status.HTTP_201_CREATED)
def create_course(data: CourseCreate, teacher: TeacherUser, db: DbSession, client: Client) -> CourseDetail:
    svc.ensure_unique_code(db, teacher, data.code)
    course = Course(teacher_id=teacher.id, **data.model_dump())
    db.add(course)
    db.flush()
    audit.record(db, "course.create", actor=teacher, entity_type="course", entity_id=course.id,
                 details={"code": course.code}, ip_address=client.ip_address)
    db.commit()
    return _course_detail(db, course)


@router.get("/courses/{course_id}", response_model=CourseDetail)
def get_course(course_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> CourseDetail:
    return _course_detail(db, svc.get_owned_course(db, teacher, course_id))


@router.put("/courses/{course_id}", response_model=CourseDetail)
def update_course(
    course_id: uuid.UUID, data: CourseUpdate, teacher: TeacherUser, db: DbSession, client: Client
) -> CourseDetail:
    course = svc.get_owned_course(db, teacher, course_id)
    svc.ensure_unique_code(db, teacher, data.code, exclude_id=course.id)
    for field, value in data.model_dump().items():
        setattr(course, field, value)
    audit.record(db, "course.update", actor=teacher, entity_type="course", entity_id=course.id,
                 details={"code": course.code}, ip_address=client.ip_address)
    db.commit()
    return _course_detail(db, course)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> Response:
    course = svc.get_owned_course(db, teacher, course_id)
    audit.record(db, "course.delete", actor=teacher, entity_type="course", entity_id=course.id,
                 details={"code": course.code}, ip_address=client.ip_address)
    db.delete(course)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/courses/{course_id}/sections", response_model=SectionRead, status_code=status.HTTP_201_CREATED)
def create_section(
    course_id: uuid.UUID, data: SectionCreate, teacher: TeacherUser, db: DbSession, client: Client
) -> SectionRead:
    course = svc.get_owned_course(db, teacher, course_id)
    svc.ensure_unique_section_name(db, course, data.name)
    section = CourseSection(course_id=course.id, name=data.name, join_code=svc.generate_join_code(db))
    db.add(section)
    db.flush()
    audit.record(db, "section.create", actor=teacher, entity_type="section", entity_id=section.id,
                 details={"code": course.code, "section": section.name}, ip_address=client.ip_address)
    db.commit()
    return _section_read(section, {})


@router.patch("/sections/{section_id}", response_model=SectionRead)
def update_section(
    section_id: uuid.UUID, data: SectionUpdate, teacher: TeacherUser, db: DbSession, client: Client
) -> SectionRead:
    section = svc.get_owned_section(db, teacher, section_id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes:
        svc.ensure_unique_section_name(db, section.course, changes["name"], exclude_id=section.id)
    for field, value in changes.items():
        setattr(section, field, value)
    audit.record(db, "section.update", actor=teacher, entity_type="section", entity_id=section.id,
                 details={**_section_details(section), "fields": sorted(changes)}, ip_address=client.ip_address)
    db.commit()
    return _section_read(section, svc.section_student_counts(db, [section.id]))


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(section_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> Response:
    section = svc.get_owned_section(db, teacher, section_id)
    audit.record(db, "section.delete", actor=teacher, entity_type="section", entity_id=section.id,
                 details=_section_details(section), ip_address=client.ip_address)
    db.delete(section)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sections/{section_id}/join-code", response_model=SectionRead)
def regenerate_join_code(section_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> SectionRead:
    section = svc.get_owned_section(db, teacher, section_id)
    section.join_code = svc.generate_join_code(db)
    audit.record(db, "section.regenerate_code", actor=teacher, entity_type="section", entity_id=section.id,
                 details=_section_details(section), ip_address=client.ip_address)
    db.commit()
    return _section_read(section, svc.section_student_counts(db, [section.id]))


@router.get("/sections/{section_id}/students", response_model=list[EnrolledStudent])
def list_section_students(section_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> list[EnrolledStudent]:
    section = svc.get_owned_section(db, teacher, section_id)
    enrollments = db.scalars(
        select(SectionEnrollment)
        .where(SectionEnrollment.section_id == section.id)
        .options(selectinload(SectionEnrollment.student))
        .join(User, SectionEnrollment.student_id == User.id)
        .order_by(User.full_name)
    ).all()
    return [
        EnrolledStudent(
            enrollment_id=e.id,
            user_id=e.student.id,
            full_name=e.student.full_name,
            email=e.student.email,
            student_id=e.student.student_id,
            joined_at=e.joined_at,
        )
        for e in enrollments
    ]


@router.delete("/sections/{section_id}/students/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_student(
    section_id: uuid.UUID, enrollment_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client
) -> Response:
    section = svc.get_owned_section(db, teacher, section_id)
    enrollment = db.get(SectionEnrollment, enrollment_id)
    if enrollment is None or enrollment.section_id != section.id:
        raise AppError(404, "Enrollment not found")
    audit.record(db, "section.remove_student", actor=teacher, entity_type="section", entity_id=section.id,
                 details={**_section_details(section), "student": enrollment.student.full_name},
                 ip_address=client.ip_address)
    db.delete(enrollment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
