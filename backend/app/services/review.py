"""Teacher review: overrides, final score calculation, approval and rejection.

AI scores are kept unchanged for the record. Teacher marks are stored next to
them; the backend alone computes each question's final mark and the final
total, and validates every value against its maximum.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.core.errors import AppError
from app.database.base import utcnow
from app.models.evaluation import Evaluation, EvaluationQuestion, ReviewStatus

ZERO = Decimal("0")


def criterion_final(criterion) -> Decimal:
    return criterion.teacher_awarded if criterion.teacher_awarded is not None else criterion.awarded


def question_final(row: EvaluationQuestion) -> Decimal | None:
    """Teacher's whole-question mark if set; otherwise the criteria (teacher's where given)."""
    if row.teacher_awarded is not None:
        return row.teacher_awarded
    if row.awarded is None:
        # Not marked by the AI: final only once the teacher has marked every criterion.
        if row.criteria and all(c.teacher_awarded is not None for c in row.criteria):
            return sum((c.teacher_awarded for c in row.criteria), ZERO)
        return None
    return sum((criterion_final(c) for c in row.criteria), ZERO) if row.criteria else row.awarded


def recompute(evaluation: Evaluation) -> None:
    finals = [question_final(q) for q in evaluation.questions]
    evaluation.final_total = None if any(v is None for v in finals) else sum(finals, ZERO)  # type: ignore[arg-type]


def refresh_flags(evaluation: Evaluation) -> None:
    flags = {flag for q in evaluation.questions for flag in q.flags}
    if any(q.awarded is None for q in evaluation.questions):
        flags.add("incomplete")
    evaluation.flags = sorted(flags)


@dataclass
class Change:
    label: str
    field: str
    old: str | None
    new: str | None

    def as_dict(self) -> dict:
        return {"question": self.label, "field": self.field, "old": self.old, "new": self.new}


def _text(value: Decimal | None) -> str | None:
    return None if value is None else f"{value.normalize():f}"


def _marks(value: float | None, maximum: Decimal, what: str) -> Decimal | None:
    if value is None:
        return None
    marks = Decimal(str(value))
    if marks.as_tuple().exponent < -2:  # type: ignore[operator]
        raise AppError(422, f"{what}: use at most two decimal places")
    if not ZERO <= marks <= maximum:
        raise AppError(422, f"{what} must be between 0 and {_text(maximum)}")
    return marks.quantize(Decimal("0.01"))


def ensure_reviewable(evaluation: Evaluation) -> None:
    if not evaluation.is_current:
        raise AppError(409, "This is an earlier evaluation run; review the current one")
    if evaluation.review_status != ReviewStatus.PENDING.value:
        raise AppError(409, "This evaluation has already been approved. Reopen it to make changes.")


def apply(evaluation: Evaluation, questions: list, comment: str | None, comment_given: bool) -> list[Change]:
    """Apply teacher overrides. `questions` items have question_id, criteria, teacher_awarded, teacher_comment."""
    ensure_reviewable(evaluation)
    rows = {q.question_id: q for q in evaluation.questions}
    changes: list[Change] = []
    for item in questions:
        row = rows.get(item.question_id)
        if row is None:
            raise AppError(422, "A reviewed question does not belong to this evaluation")
        criteria = {c.id: c for c in row.criteria}
        for edit in item.criteria:
            criterion = criteria.get(edit.criterion_id)
            if criterion is None:
                raise AppError(422, f"Unknown criterion for question {row.label}")
            new = _marks(edit.teacher_awarded, criterion.max_marks, f"{row.label} · {criterion.name}")
            if new != criterion.teacher_awarded:
                changes.append(Change(row.label, f"criterion '{criterion.name}'", _text(criterion.teacher_awarded), _text(new)))
                criterion.teacher_awarded = new
        if "teacher_awarded" in item.model_fields_set:
            new = _marks(item.teacher_awarded, row.max_marks, f"Question {row.label}")
            if new != row.teacher_awarded:
                changes.append(Change(row.label, "question mark", _text(row.teacher_awarded), _text(new)))
                row.teacher_awarded = new
        if "teacher_comment" in item.model_fields_set:
            new_comment = (item.teacher_comment or "").strip() or None
            if new_comment != row.teacher_comment:
                changes.append(Change(row.label, "comment", None, "updated" if new_comment else "removed"))
                row.teacher_comment = new_comment
    if comment_given:
        new_comment = (comment or "").strip() or None
        if new_comment != evaluation.teacher_comment:
            changes.append(Change("overall", "comment", None, "updated" if new_comment else "removed"))
            evaluation.teacher_comment = new_comment
    recompute(evaluation)
    return changes


def approve(evaluation: Evaluation, teacher_id) -> None:
    ensure_reviewable(evaluation)
    recompute(evaluation)
    missing = [q.label for q in evaluation.questions if question_final(q) is None]
    if missing:
        raise AppError(422, f"Give marks for question {', '.join(missing)} before approving")
    evaluation.review_status = ReviewStatus.APPROVED.value
    evaluation.reviewed_by_id = teacher_id
    evaluation.reviewed_at = utcnow()


def is_clean(evaluation: Evaluation) -> bool:
    """No flags at all except plain unanswered questions."""
    return all(flag == "missing_answer" for flag in evaluation.flags) and evaluation.final_total is not None
