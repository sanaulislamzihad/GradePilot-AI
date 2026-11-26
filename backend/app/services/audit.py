"""Audit trail helpers.

Callers add the entry to the current session; it is committed together with the
change it describes, so the log never records something that was rolled back.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User

# Human-readable templates. `{name}`-style keys are filled from `details`.
_SUMMARIES: dict[str, str] = {
    "auth.register": "Created a {role} account",
    "auth.login": "Signed in",
    "auth.login_failed": "Failed sign-in attempt",
    "auth.logout": "Signed out",
    "auth.refresh_reuse": "Refresh token reuse detected; sessions revoked",
    "user.profile_update": "Updated profile",
    "user.password_change": "Changed password",
    "admin.user_update": "Updated user {target_email}",
    "course.create": "Created course {code}",
    "course.update": "Updated course {code}",
    "course.delete": "Deleted course {code}",
    "section.create": "Added section {section} to {code}",
    "section.update": "Updated section {section} of {code}",
    "section.delete": "Deleted section {section} of {code}",
    "section.regenerate_code": "Generated a new join code for {code} section {section}",
    "section.remove_student": "Removed {student} from {code} section {section}",
    "enrollment.join": "Joined {code} section {section}",
    "exam.create": "Created exam {title}",
    "exam.update": "Updated exam {title}",
    "exam.delete": "Deleted exam {title}",
    "exam.question_paper_upload": "Uploaded the question paper for {title}",
    "exam.questions_extract": "Extracted {questions} questions for {title}",
    "exam.model_answer_upload": "Uploaded model answers for {title}",
    "exam.publish": "Published exam {title}",
    "exam.unpublish": "Unpublished exam {title}",
    "submission.create": "Submitted attempt {attempt} for {title} ({code})",
    "enrollment.leave": "Left {code} section {section}",
}


def record(
    db: Session,
    action: str,
    *,
    actor: User | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        details=details or None,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry


def describe(entry: AuditLog) -> str:
    template = _SUMMARIES.get(entry.action)
    if template is None:
        return entry.action
    try:
        return template.format(**(entry.details or {}))
    except (KeyError, IndexError):
        return template.split(" {")[0]
