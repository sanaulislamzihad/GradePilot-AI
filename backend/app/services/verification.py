"""Stage 5: independent checks of an AI evaluation before the teacher sees it.

Local checks always run: a SymPy check for mathematical questions and a
semantic-similarity signal for written answers. When a verifier model is set
up, it audits every marked question independently. Disagreement is never
averaged away: it becomes a review flag for the teacher.
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import ModelSlot
from app.models.evaluation import (
    AnswerStatus,
    Evaluation,
    EvaluationQuestion,
    ExtractedAnswer,
    VerificationResult,
    VerificationStatus,
    VerifierVerdict,
)
from app.models.exam import Exam, Question, QuestionType
from app.providers.base import AIError, AIRequest
from app.services import ai_router, math_check, review, similarity
from app.services.exam_service import fmt
from app.services.prompts import VERIFICATION_SCHEMA, VERIFICATION_SYSTEM, VerificationReport, verification_prompt

logger = logging.getLogger("gradepilot.verification")

FLAG_MATH_DISAGREES = "math_disagrees"
FLAG_MATH_UNCERTAIN = "math_uncertain"
FLAG_SIMILARITY = "similarity_mismatch"
FLAG_VERIFIER = "verifier_disagrees"
FLAG_VERIFICATION_FAILED = "verification_failed"
VERIFICATION_FLAGS = {FLAG_MATH_DISAGREES, FLAG_MATH_UNCERTAIN, FLAG_SIMILARITY, FLAG_VERIFIER, FLAG_VERIFICATION_FAILED}

# Similarity thresholds for "marks and content disagree" (signal only).
HIGH_MARKS, LOW_MARKS = Decimal("0.8"), Decimal("0.2")
LOW_SIMILARITY, HIGH_SIMILARITY = 0.25, 0.85


def disagreement_threshold(max_marks: Decimal) -> Decimal:
    """Differences at least this large between examiners need a teacher: 20% of the marks, minimum 1."""
    return max(Decimal("1"), (max_marks * Decimal("0.2")).quantize(Decimal("0.01")))


def _ratio(awarded: Decimal, maximum: Decimal) -> Decimal:
    return awarded / maximum if maximum else Decimal("0")


def _add_flag(row: EvaluationQuestion, flag: str) -> None:
    if flag not in row.flags:
        row.flags = sorted({*row.flags, flag})


def _local_checks(row: EvaluationQuestion, question: Question, answer_text: str) -> list[str]:
    """Run SymPy and similarity checks; return notes for the verifier prompt."""
    notes: list[str] = []
    assert row.awarded is not None and question.model_answer is not None
    ratio = _ratio(row.awarded, row.max_marks)

    if question.question_type == QuestionType.MATHEMATICAL.value:
        result = math_check.check(question.model_answer.content, answer_text)
        row.math_check = result.as_dict()
        if result.status == "uncertain":
            _add_flag(row, FLAG_MATH_UNCERTAIN)
        elif (result.status == "mismatch" and ratio > Decimal("0.5")) or (result.status == "match" and ratio < Decimal("0.5")):
            _add_flag(row, FLAG_MATH_DISAGREES)
        notes.append(f"SymPy check: {result.detail}")
        for step in result.step_errors:
            notes.append(f"SymPy: line {step['line']} of the working does not hold: {step['text']}")
    else:
        value = similarity.score(answer_text, question.model_answer.content)
        row.similarity = value
        if value is not None and ((ratio >= HIGH_MARKS and value < LOW_SIMILARITY) or (ratio <= LOW_MARKS and value >= HIGH_SIMILARITY)):
            _add_flag(row, FLAG_SIMILARITY)
    return notes


def _verify_question(config, evaluation: Evaluation, row: EvaluationQuestion, question: Question,
                     answer_text: str, notes: list[str]) -> VerificationResult:
    criteria = list(row.criteria)
    ids = {f"C{i}": c for i, c in enumerate(criteria, start=1)}
    same_model = config.api_key.provider.slug == evaluation.provider and config.model == evaluation.model

    def check(parsed: VerificationReport) -> None:
        if sorted(c.id for c in parsed.criteria) != sorted(ids):
            raise ValueError(f"Return exactly one entry for each criterion id: {', '.join(ids)}")
        for audit in parsed.criteria:
            maximum = ids[audit.id].max_marks
            if not 0 <= audit.suggested_awarded <= float(maximum):
                raise ValueError(f"{audit.id} suggested {audit.suggested_awarded}, but it must be between 0 and {fmt(maximum)}")

    prompt = verification_prompt(
        question=question.text, max_marks=fmt(row.max_marks), model_answer=question.model_answer.content,
        answer=answer_text,
        criteria=[
            (cid, c.name, c.rubric_criterion.description if c.rubric_criterion else None, fmt(c.max_marks), fmt(c.awarded),
             [e.quote for e in c.evidence], c.explanation)
            for cid, c in ids.items()
        ],
        signals=notes,
    )
    result = VerificationResult(
        provider=config.api_key.provider.slug, model=config.model, same_model_as_evaluator=same_model,
        verdict=VerifierVerdict.FAILED.value, missed_valid_concepts=[], unsupported_assumptions=[], criterion_notes=[],
    )
    try:
        report, _ = ai_router.call_json(
            config,
            AIRequest(system=VERIFICATION_SYSTEM, prompt=prompt, json_schema=VERIFICATION_SCHEMA, max_tokens=3000),
            VerificationReport,
            ai_router.TaskContext(task="verify_evaluation", submission_id=evaluation.submission_id),
            extra_check=check,
        )
    except AIError as exc:
        result.comment = exc.message
        _add_flag(row, FLAG_VERIFICATION_FAILED)
        return result

    suggested = sum((Decimal(str(a.suggested_awarded)).quantize(Decimal("0.01")) for a in report.criteria), Decimal("0"))
    assert row.awarded is not None
    disagrees = (
        abs(suggested - row.awarded) >= disagreement_threshold(row.max_marks)
        or not report.rubric_followed
        or not report.evidence_supports_marks
    )
    result.verdict = (VerifierVerdict.DISAGREES if disagrees else VerifierVerdict.AGREES).value
    result.suggested_awarded = suggested
    result.rubric_followed = report.rubric_followed
    result.evidence_supports_marks = report.evidence_supports_marks
    result.missed_valid_concepts = [m.strip() for m in report.missed_valid_concepts if m.strip()]
    result.unsupported_assumptions = [m.strip() for m in report.unsupported_assumptions if m.strip()]
    result.criterion_notes = [
        {"criterion": ids[a.id].name, "fair": a.fair, "suggested_awarded": a.suggested_awarded, "note": a.note.strip()}
        for a in report.criteria
    ]
    result.comment = report.comment.strip() or None
    if disagrees:
        _add_flag(row, FLAG_VERIFIER)
    return result


def verify(db: Session, evaluation: Evaluation) -> None:
    """Run all checks on an evaluation and refresh its flags and final total. Never raises for AI failures."""
    submission = evaluation.submission
    exam: Exam = submission.exam
    questions = {q.id: q for q in exam.questions}
    answers = {
        a.question_id: a.text
        for a in db.scalars(select(ExtractedAnswer).where(ExtractedAnswer.submission_id == submission.id))
    }
    config = None
    if ai_router.has_slot(db, exam.teacher_id, ModelSlot.VERIFIER):
        config = ai_router.slot_config(db, exam.teacher_id, ModelSlot.VERIFIER)

    # Re-running replaces earlier output. Delete old results first (they are unique
    # per question) and commit, so no write transaction stays open during the AI
    # calls: usage logging writes from its own session, which SQLite would block.
    for row in evaluation.questions:
        if row.verification is not None:
            db.delete(row.verification)
            row.verification = None
        row.flags = [f for f in row.flags if f not in VERIFICATION_FLAGS]
    db.commit()

    attempted = failed = 0
    for row in evaluation.questions:
        question = questions.get(row.question_id)
        text = answers.get(row.question_id, "")
        if question is None or row.awarded is None or row.answer_status != AnswerStatus.ANSWERED.value or not text.strip():
            continue
        try:
            notes = _local_checks(row, question, text)
        except Exception:  # noqa: BLE001 - a local check must never block review
            logger.exception("Local checks failed for evaluation %s", evaluation.id)
            notes = []
        if config is not None:
            attempted += 1
            row.verification = _verify_question(config, evaluation, row, question, text, notes)
            failed += row.verification.verdict == VerifierVerdict.FAILED.value

    if config is None:
        evaluation.verification_status = VerificationStatus.SKIPPED.value
    elif attempted and failed == attempted:
        evaluation.verification_status = VerificationStatus.FAILED.value
    else:
        evaluation.verification_status = VerificationStatus.COMPLETED.value
    review.refresh_flags(evaluation)
    review.recompute(evaluation)
