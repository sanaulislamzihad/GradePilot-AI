import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.models.user import UserRole
from app.schemas.common import ORMModel

FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
OptionalText160 = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=160)]
OptionalText120 = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=120)]
StudentIdText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=40, pattern=r"^[A-Za-z0-9\-_/]+$")
]


def validate_password_strength(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters long")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password must contain at least one letter and one number")
    return password


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class UserRead(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    student_id: str | None
    institution: str | None
    department: str | None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: FullName
    # Admin accounts are never self-registered; they are created from the CLI.
    role: Literal["teacher", "student"]
    student_id: StudentIdText | None = None
    institution: OptionalText160 = None
    department: OptionalText120 = None

    _blank = field_validator("student_id", "institution", "department", mode="before")(_blank_to_none)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode="after")
    def _student_needs_id(self) -> "RegisterRequest":
        if self.role == "student" and not self.student_id:
            raise ValueError("Student ID is required for student accounts")
        if self.role != "student":
            self.student_id = None
        return self


class ProfileUpdate(BaseModel):
    full_name: FullName | None = None
    institution: OptionalText160 = None
    department: OptionalText120 = None

    _blank = field_validator("institution", "department", mode="before")(_blank_to_none)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, value: str) -> str:
        return validate_password_strength(value)


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
