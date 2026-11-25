"""Registration, login and refresh-token session management."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.database.base import as_utc, utcnow
from app.models.user import RefreshToken, User, UserRole
from app.schemas.user import RegisterRequest
from app.security.passwords import hash_password, needs_rehash, verify_password
from app.security.tokens import create_access_token, generate_refresh_token, hash_refresh_token
from app.services import audit


REUSE_GRACE_PERIOD = timedelta(seconds=30)


class StaleRefreshTokenError(AppError):
    """A just-rotated token was replayed by a concurrent request from the same browser."""


@dataclass
class IssuedSession:
    access_token: str
    expires_in: int
    refresh_token: str
    user: User


@dataclass
class ClientInfo:
    ip_address: str | None
    user_agent: str | None


def register_user(db: Session, data: RegisterRequest, client: ClientInfo) -> User:
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise AppError(409, "An account with this email already exists")
    if data.student_id and db.scalar(select(User.id).where(User.student_id == data.student_id)):
        raise AppError(409, "This student ID is already registered")

    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=UserRole(data.role),
        student_id=data.student_id,
        institution=data.institution,
        department=data.department,
    )
    db.add(user)
    db.flush()
    audit.record(
        db, "auth.register", actor=user, entity_type="user", entity_id=user.id,
        details={"role": user.role.value}, ip_address=client.ip_address,
    )
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str, client: ClientInfo) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if not verify_password(password, user.password_hash if user else None) or user is None:
        if user is not None:
            audit.record(db, "auth.login_failed", actor=user, ip_address=client.ip_address)
            db.commit()
        raise AppError(401, "Incorrect email or password")
    if not user.is_active:
        raise AppError(403, "This account has been deactivated. Contact an administrator.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = utcnow()
    audit.record(db, "auth.login", actor=user, ip_address=client.ip_address)
    return user


def issue_session(
    db: Session, user: User, client: ClientInfo, family_id: uuid.UUID | None = None
) -> IssuedSession:
    """Create a refresh token row and an access token, then commit."""
    settings = get_settings()
    raw_refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
            user_agent=(client.user_agent or "")[:255] or None,
            ip_address=client.ip_address,
        )
    )
    access_token, expires_in = create_access_token(user)
    db.commit()
    return IssuedSession(access_token, expires_in, raw_refresh, user)


def rotate_refresh_token(db: Session, raw_token: str, client: ClientInfo) -> IssuedSession:
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)))
    if stored is None:
        raise AppError(401, "Session expired. Please sign in again.")

    if stored.revoked_at is not None:
        if utcnow() - as_utc(stored.revoked_at) < REUSE_GRACE_PERIOD:
            # Two tabs refreshing at once share one cookie; the slower request
            # arrives with the token the faster one just rotated. Not an attack.
            raise StaleRefreshTokenError(401, "Session was refreshed in another tab. Retry.")
        # A rotated token was presented again long after rotation: it may have
        # been stolen. Revoke every token in this login family.
        revoke_family(db, stored.family_id)
        audit.record(db, "auth.refresh_reuse", actor=stored.user, ip_address=client.ip_address)
        db.commit()
        raise AppError(401, "Session expired. Please sign in again.")

    if as_utc(stored.expires_at) <= utcnow():
        raise AppError(401, "Session expired. Please sign in again.")

    user = stored.user
    if not user.is_active:
        revoke_family(db, stored.family_id)
        db.commit()
        raise AppError(403, "This account has been deactivated. Contact an administrator.")

    stored.revoked_at = utcnow()
    return issue_session(db, user, client, family_id=stored.family_id)


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def revoke_all_sessions(db: Session, user: User) -> None:
    """Revoke refresh tokens and invalidate outstanding access tokens."""
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    user.token_version += 1


def logout(db: Session, raw_token: str | None, user: User | None, client: ClientInfo) -> None:
    if raw_token:
        stored = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        )
        if stored is not None:
            revoke_family(db, stored.family_id)
            user = user or stored.user
    if user is not None:
        audit.record(db, "auth.logout", actor=user, ip_address=client.ip_address)
    db.commit()
