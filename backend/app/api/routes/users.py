from fastapi import APIRouter, Depends, Response

from app.api.deps import Client, CurrentUser, DbSession, rate_limit_auth
from app.api.session_cookies import token_response
from app.core.errors import AppError
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.user import PasswordChange, ProfileUpdate, UserRead
from app.security.passwords import hash_password, verify_password
from app.services import audit
from app.services.auth_service import issue_session, revoke_all_sessions

router = APIRouter(prefix="/users", tags=["profile"])


@router.patch("/me", response_model=UserRead)
def update_profile(data: ProfileUpdate, user: CurrentUser, db: DbSession, client: Client) -> User:
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes and changes["full_name"] is None:
        raise AppError(422, "Full name cannot be empty")
    for field, value in changes.items():
        setattr(user, field, value)
    if changes:
        audit.record(
            db, "user.profile_update", actor=user, entity_type="user", entity_id=user.id,
            details={"fields": sorted(changes)}, ip_address=client.ip_address,
        )
    db.commit()
    return user


@router.post("/me/password", response_model=TokenResponse, dependencies=[Depends(rate_limit_auth)])
def change_password(
    data: PasswordChange, response: Response, user: CurrentUser, db: DbSession, client: Client
) -> TokenResponse:
    if not verify_password(data.current_password, user.password_hash):
        raise AppError(400, "Current password is incorrect")
    if verify_password(data.new_password, user.password_hash):
        raise AppError(400, "New password must be different from the current password")

    user.password_hash = hash_password(data.new_password)
    # Sign out every other device; this device gets a fresh session.
    revoke_all_sessions(db, user)
    audit.record(db, "user.password_change", actor=user, entity_type="user", entity_id=user.id,
                 ip_address=client.ip_address)
    return token_response(response, issue_session(db, user, client))
