import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UTCDateTime, Timestamps, UUIDPrimaryKey, utcnow
from app.models.user import User


class Course(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("teacher_id", "code", name="uq_courses_teacher_code"),)

    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    teacher: Mapped[User] = relationship()
    sections: Mapped[list["CourseSection"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="CourseSection.name"
    )


class CourseSection(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "course_sections"
    __table_args__ = (UniqueConstraint("course_id", "name", name="uq_course_sections_course_name"),)

    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    # Students join a section by entering this code.
    join_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    course: Mapped[Course] = relationship(back_populates="sections")
    enrollments: Mapped[list["SectionEnrollment"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )


class SectionEnrollment(UUIDPrimaryKey, Base):
    __tablename__ = "section_enrollments"
    __table_args__ = (
        UniqueConstraint("section_id", "student_id", name="uq_section_enrollments_section_student"),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_sections.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    joined_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    section: Mapped[CourseSection] = relationship(back_populates="enrollments")
    student: Mapped[User] = relationship()
