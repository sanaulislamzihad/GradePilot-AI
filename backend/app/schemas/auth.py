from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenResponse(BaseModel):
    """The refresh token is never in the body; it is set as an httpOnly cookie."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
