"""Admin-only user management and system monitoring."""

import time
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import selectinload

from app import __version__
from app.api.deps import AdminUser, Client, DbSession
from app.core.config import get_settings
from app.core.errors import AppError
from app.database.base import utcnow
from app.models.audit_log import AuditLog
from app.models.course import Course, CourseSection, SectionEnrollment
from app.models.exam import Exam
from app.models.user import RefreshToken, User, UserRole
from app.schemas.common import Page
from app.schemas.dashboard import AdminOverview, AuditLogRead, SystemStatus
from app.schemas.user import AdminUserUpdate, UserRead
from app.services import audit
from app.services.auth_service import revoke_all_sessions

router = APIRouter(prefix="/admin", tags=["admin"])

_STARTED_AT = time.monotonic()


@router.get("/overview", response_model=AdminOverview)
def overview(_: AdminUser, db: DbSession) -> AdminOverview:
    by_role = dict(db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all())
    return AdminOverview(
        total_users=sum(by_role.values()),
        active_users=db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0,
        users_by_role={role: by_role.get(role, 0) for role in UserRole},
        course_count=db.scalar(select(func.count(Course.id))) or 0,
        section_count=db.scalar(select(func.count(CourseSection.id))) or 0,
        enrollment_count=db.scalar(select(func.count(SectionEnrollment.id))) or 0,
        new_users_last_7_days=db.scalar(
            select(func.count(User.id)).where(User.created_at >= utcnow() - timedelta(days=7))
        ) or 0,
    )


@router.get("/users", response_model=Page[UserRead])
def list_users(
    _: AdminUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[UserRead]:
    query = select(User)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(User.full_name.ilike(term), User.email.ilike(term), User.student_id.ilike(term)))
    if role is not None:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active.is_(is_active))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    users = db.scalars(
        query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(items=[UserRead.model_validate(u) for u in users], total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID, data: AdminUserUpdate, admin: AdminUser, db: DbSession, client: Client
) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise AppError(404, "User not found")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        return target
    if target.id == admin.id:
        raise AppError(400, "You cannot change your own role or status")

    new_role = changes.get("role")
    if new_role is not None and new_role != target.role:
        if new_role == UserRole.STUDENT and not target.student_id:
            raise AppError(400, "This user has no student ID, so they cannot become a student")
        if target.role == UserRole.TEACHER and (
            db.scalar(select(Course.id).where(Course.teacher_id == target.id))
            or db.scalar(select(Exam.id).where(Exam.teacher_id == target.id))
        ):
            raise AppError(409, "This teacher still owns courses or exams. Delete them first.")
        if target.role == UserRole.STUDENT:
            for enrollment in db.scalars(select(SectionEnrollment).where(SectionEnrollment.student_id == target.id)):
                db.delete(enrollment)

    session_affected = (new_role is not None and new_role != target.role) or changes.get("is_active") is False
    for field, value in changes.items():
        setattr(target, field, value)
    if session_affected:
        # Role changes and deactivation end every existing session immediately.
        revoke_all_sessions(db, target)

    audit.record(
        db, "admin.user_update", actor=admin, entity_type="user", entity_id=target.id,
        details={"target_email": target.email, **{k: (v.value if isinstance(v, UserRole) else v) for k, v in changes.items()}},
        ip_address=client.ip_address,
    )
    db.commit()
    return target


@router.get("/audit-logs", response_model=Page[AuditLogRead])
def audit_logs(
    _: AdminUser,
    db: DbSession,
    action: Annotated[str | None, Query(max_length=60)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[AuditLogRead]:
    query = select(AuditLog)
    if action:
        # Prefix match, so "auth" returns every auth.* event.
        query = query.where(AuditLog.action.startswith(action.strip()))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    entries = db.scalars(
        query.options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        AuditLogRead(
            id=e.id,
            action=e.action,
            summary=audit.describe(e),
            actor_name=e.actor.full_name if e.actor else None,
            actor_email=e.actor.email if e.actor else None,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            ip_address=e.ip_address,
            created_at=e.created_at,
        )
        for e in entries
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/system", response_model=SystemStatus)
def system_status(_: AdminUser, db: DbSession) -> SystemStatus:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
    except Exception:  # noqa: BLE001 - reported as unhealthy, not raised
        database_ok, revision = False, None
        db.rollback()

    storage_writable = False
    try:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.storage_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        storage_writable = True
    except OSError:
        pass

    active_sessions = 0
    if database_ok:
        active_sessions = db.scalar(
            select(func.count(RefreshToken.id)).where(
                RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > utcnow()
            )
        ) or 0

    return SystemStatus(
        status="ok" if database_ok and storage_writable else "degraded",
        version=__version__,
        environment=settings.environment,
        database_backend=db.get_bind().dialect.name,
        database_ok=database_ok,
        migration_revision=revision,
        uptime_seconds=int(time.monotonic() - _STARTED_AT),
        storage_writable=storage_writable,
        active_sessions=active_sessions,
    )
