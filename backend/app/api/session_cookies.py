"""Refresh-token cookie handling shared by auth and profile routes."""

from typing import Annotated

from fastapi import Cookie, Response

from app.core.config import get_settings
from app.schemas.auth import TokenResponse
from app.schemas.user import UserRead
from app.services.auth_service import IssuedSession

settings = get_settings()

# The cookie is only ever sent to the auth endpoints, never to the rest of the API.
REFRESH_COOKIE_PATH = f"{settings.api_prefix}/auth"
RefreshCookie = Annotated[str | None, Cookie(alias=settings.refresh_cookie_name)]


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def token_response(response: Response, session: IssuedSession) -> TokenResponse:
    set_refresh_cookie(response, session.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        access_token=session.access_token,
        expires_in=session.expires_in,
        user=UserRead.model_validate(session.user),
    )
