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
from app.security.rate_limit import SlidingWindowLimiter
from app.security.tokens import InvalidTokenError, decode_access_token
from app.services.auth_service import ClientInfo

DbSession = Annotated[Session, Depends(get_db)]

bearer_scheme = HTTPBearer(auto_error=False)
_settings = get_settings()
auth_limiter = SlidingWindowLimiter(
    _settings.auth_rate_limit_attempts, _settings.auth_rate_limit_window_seconds
)

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


def rate_limit_auth(request: Request) -> None:
    key = f"{request.url.path}:{request.client.host if request.client else 'unknown'}"
    retry_after = auth_limiter.hit(key)
    if retry_after is not None:
        raise AppError(
            429,
            "Too many attempts. Please wait a few minutes and try again.",
            headers={"Retry-After": str(retry_after)},
        )
