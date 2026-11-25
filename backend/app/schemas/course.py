import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from app.schemas.common import ORMModel

CourseCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=2, max_length=30, pattern=r"^[A-Za-z0-9\-\s]+$")
]
CourseName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
SectionName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
JoinCode = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=4, max_length=12)]


class CourseCreate(BaseModel):
    code: CourseCode
    name: CourseName
    description: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=2000)] = None

    @field_validator("description", mode="before")
    @classmethod
    def _blank(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


class CourseUpdate(CourseCreate):
    pass


class SectionCreate(BaseModel):
    name: SectionName


class SectionUpdate(BaseModel):
    name: SectionName | None = None
    is_open: bool | None = None


class SectionRead(ORMModel):
    id: uuid.UUID
    course_id: uuid.UUID
    name: str
    join_code: str
    is_open: bool
    student_count: int = 0
    created_at: datetime


class CourseRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    section_count: int = 0
    student_count: int = 0


class CourseDetail(CourseRead):
    sections: list[SectionRead]


class EnrolledStudent(BaseModel):
    enrollment_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    student_id: str | None
    joined_at: datetime


class JoinSectionRequest(BaseModel):
    join_code: JoinCode


class StudentEnrollment(BaseModel):
    enrollment_id: uuid.UUID
    section_id: uuid.UUID
    section_name: str
    course_id: uuid.UUID
    course_code: str
    course_name: str
    teacher_name: str
    joined_at: datetime
