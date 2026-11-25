from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import Client, CurrentUser, DbSession, bearer_scheme, rate_limit_auth
from app.api.session_cookies import RefreshCookie, clear_refresh_cookie, token_response
from app.core.errors import AppError
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import RegisterRequest, UserRead
from app.security.tokens import InvalidTokenError, decode_access_token
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth)],
)
def register(data: RegisterRequest, response: Response, db: DbSession, client: Client) -> TokenResponse:
    user = auth_service.register_user(db, data, client)
    return token_response(response, auth_service.issue_session(db, user, client))


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit_auth)])
def login(data: LoginRequest, response: Response, db: DbSession, client: Client) -> TokenResponse:
    user = auth_service.authenticate(db, data.email, data.password, client)
    return token_response(response, auth_service.issue_session(db, user, client))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response, db: DbSession, client: Client, refresh_token: RefreshCookie = None
) -> TokenResponse:
    if not refresh_token:
        raise AppError(401, "Not signed in")
    try:
        session = auth_service.rotate_refresh_token(db, refresh_token, client)
    except auth_service.StaleRefreshTokenError:
        # Keep the cookie: the browser already holds the newer token.
        raise
    except AppError as exc:
        # Drop the dead cookie so the browser stops sending it.
        failure = Response(status_code=exc.status_code)
        clear_refresh_cookie(failure)
        exc.headers = {**(exc.headers or {}), "set-cookie": failure.headers["set-cookie"]}
        raise
    return token_response(response, session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: DbSession,
    client: Client,
    refresh_token: RefreshCookie = None,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> Response:
    # Logout works even with an expired access token; the cookie identifies the session.
    user = None
    if credentials is not None:
        try:
            user = db.get(User, decode_access_token(credentials.credentials).user_id)
        except InvalidTokenError:
            user = None
    auth_service.logout(db, refresh_token, user, client)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user
