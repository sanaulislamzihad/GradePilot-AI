"""Access tokens (short-lived JWT) and refresh tokens (opaque, hashed at rest)."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt

from app.core.config import get_settings
from app.database.base import utcnow
from app.models.user import User, UserRole

ACCESS_TOKEN_TYPE = "access"


class InvalidTokenError(Exception):
    pass


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    role: UserRole
    token_version: int


def create_access_token(user: User) -> tuple[str, int]:
    """Return the encoded token and its lifetime in seconds."""
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    now = utcnow()
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "ver": user.token_version,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "type", "ver"]},
        )
        if payload.get("type") != ACCESS_TOKEN_TYPE:
            raise InvalidTokenError("Wrong token type")
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            role=UserRole(payload["role"]),
            token_version=int(payload["ver"]),
        )
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise InvalidTokenError("Invalid or expired access token") from exc


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
