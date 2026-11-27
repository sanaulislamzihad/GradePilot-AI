"""Shared FastAPI dependencies: database session, current user and role checks."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.database.session import get_db
from app.models.user import User, UserRole
from app.security.rate_limit import Limiter, build_limiter
from app.security.tokens import InvalidTokenError, decode_access_token
from app.services.auth_service import ClientInfo

DbSession = Annotated[Session, Depends(get_db)]

bearer_scheme = HTTPBearer(auto_error=False)
_settings = get_settings()
auth_limiter = build_limiter(
    "auth", _settings.auth_rate_limit_attempts, _settings.auth_rate_limit_window_seconds, _settings.rate_limit_redis_url
)
upload_limiter = build_limiter(
    "upload", _settings.upload_rate_limit_attempts, _settings.upload_rate_limit_window_seconds, _settings.rate_limit_redis_url
)
ai_limiter = build_limiter(
    "ai", _settings.ai_rate_limit_attempts, _settings.ai_rate_limit_window_seconds, _settings.rate_limit_redis_url
)
LIMITERS = (auth_limiter, upload_limiter, ai_limiter)

_UNAUTHENTICATED = AppError(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})


def client_info(request: Request) -> ClientInfo:
    return ClientInfo(
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


Client = Annotated[ClientInfo, Depends(client_info)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _UNAUTHENTICATED
    try:
        claims = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _UNAUTHENTICATED from None

    user = db.get(User, claims.user_id)
    # The token version check rejects tokens issued before a password change,
    # role change or deactivation. The role always comes from the database.
    if user is None or not user.is_active or user.token_version != claims.token_version:
        raise _UNAUTHENTICATED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    def _checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError(403, "You do not have permission to perform this action")
        return user

    return _checker


TeacherUser = Annotated[User, Depends(require_roles(UserRole.TEACHER))]
StudentUser = Annotated[User, Depends(require_roles(UserRole.STUDENT))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


def _enforce(limiter: Limiter, key: str, message: str) -> None:
    retry_after = limiter.hit(key)
    if retry_after is not None:
        raise AppError(429, message, headers={"Retry-After": str(retry_after)})


def rate_limit_auth(request: Request) -> None:
    """Credential endpoints, per client IP (see the proxy notes in the README)."""
    ip = request.client.host if request.client else "unknown"
    _enforce(auth_limiter, f"{request.url.path}:{ip}", "Too many attempts. Please wait a few minutes and try again.")


def rate_limit_upload(user: CurrentUser) -> None:
    """Answer script uploads, per student."""
    _enforce(upload_limiter, str(user.id), "Too many uploads in a short time. Please wait a few minutes and try again.")


def rate_limit_ai(user: CurrentUser) -> None:
    """Requests that start AI work (marking, drafting, provider checks), per user."""
    _enforce(ai_limiter, str(user.id), "Too many AI requests in a short time. Please wait a few minutes and try again.")
