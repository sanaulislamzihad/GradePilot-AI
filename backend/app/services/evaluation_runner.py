"""Stage 3 and 6: rubric-based evaluation with backend score validation.

Each question is marked separately against its approved rubric. The backend
checks every criterion score (known criterion, number within 0..max), checks
that quoted evidence really appears in the student's answer, and computes all
totals itself. A model-reported total is never used.
"""

import re
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models.ai import ModelSlot
from app.models.evaluation import (
    AnswerStatus,
    Evaluation,
    EvaluationCriterion,
    EvaluationEvidence,
    EvaluationQuestion,
    EvaluationStatus,
    ExtractedAnswer,
)
from app.models.exam import QuestionType
from app.models.submission import Submission
from app.providers.base import AIInvalidResponseError, AIRequest
from app.services import ai_router
from app.services.exam_service import fmt, leaves
from app.services.prompts import EVALUATION_SCHEMA, EVALUATION_SYSTEM, QuestionScore, evaluation_prompt

ZERO = Decimal("0")
CENT = Decimal("0.01")

FLAG_MISSING = "missing_answer"
FLAG_UNREADABLE = "unreadable_answer"
FLAG_INVALID_OUTPUT = "invalid_ai_output"
FLAG_NO_EVIDENCE = "evidence_not_found"
FLAG_INCOMPLETE = "incomplete"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[“”\"'‘’`]", "", text)).strip().lower()


def evidence_found(quote: str, answer: str) -> bool:
    quote_n = _norm(quote).strip(" .,;:")
    return bool(quote_n) and quote_n in _norm(answer)


def _marks(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def evaluate(db: Session, submission: Submission) -> Evaluation:
    exam = submission.exam
    config = ai_router.slot_config(db, exam.teacher_id, ModelSlot.EVALUATOR)
    answers = {
        a.question_id: a
        for a in db.scalars(select(ExtractedAnswer).where(ExtractedAnswer.submission_id == submission.id))
    }
    gradable = list(leaves(exam))
    run_number = (db.scalar(select(func.max(Evaluation.run_number)).where(Evaluation.submission_id == submission.id)) or 0) + 1
    evaluation = Evaluation(
        submission_id=submission.id,
        run_number=run_number,
        is_current=False,
        status=EvaluationStatus.COMPLETED.value,
        provider=config.api_key.provider.slug,
        model=config.model,
        total_max=sum((q.marks or ZERO for q, _ in gradable), ZERO),
        flags=[],
    )
    context = ai_router.TaskContext(task="evaluate_answer", submission_id=submission.id, exam_id=exam.id)
    all_flags: set[str] = set()

    for position, (question, label) in enumerate(gradable, start=1):
        rubric = question.rubric
        assert rubric is not None and question.marks is not None and question.model_answer is not None
        criteria = list(rubric.criteria)
        answer = answers.get(question.id)
        status = AnswerStatus(answer.status) if answer else AnswerStatus.MISSING
        row = EvaluationQuestion(
            question_id=question.id, position=position, label=label, answer_status=status.value,
            max_marks=question.marks, missing_concepts=[], flags=[],
        )
        evaluation.questions.append(row)

        if status == AnswerStatus.MISSING or not (answer and answer.text.strip()):
            if status == AnswerStatus.UNREADABLE:
                # Unreadable is not the same as unanswered: a teacher decides.
                row.awarded = None
                row.flags = [FLAG_UNREADABLE]
                row.feedback = None
            else:
                row.awarded = ZERO
                row.flags = [FLAG_MISSING]
                row.feedback = "No answer was found for this question."
                for index, criterion in enumerate(criteria, start=1):
                    row.criteria.append(EvaluationCriterion(
                        rubric_criterion_id=criterion.id, position=index, name=criterion.name,
                        max_marks=criterion.max_marks, awarded=ZERO,
                        explanation="No answer was given.", missing_concepts=[],
                    ))
            all_flags.update(row.flags)
            continue

        ids = {f"C{i}": c for i, c in enumerate(criteria, start=1)}

        def check(parsed: QuestionScore) -> None:
            returned = [c.id for c in parsed.criteria]
            if sorted(returned) != sorted(ids):
                raise ValueError(f"Return exactly one entry for each criterion id: {', '.join(ids)}")
            for score in parsed.criteria:
                maximum = ids[score.id].max_marks
                if not 0 <= score.awarded <= float(maximum):
                    raise ValueError(f"{score.id} awarded {score.awarded}, but it must be between 0 and {fmt(maximum)}")

        prompt = evaluation_prompt(
            question=question.text,
            max_marks=fmt(question.marks),
            question_type=QuestionType(question.question_type).value.replace("_", " "),
            model_answer=question.model_answer.content,
            criteria=[(cid, c.name, c.description, fmt(c.max_marks)) for cid, c in ids.items()],
            answer=answer.text,
        )
        try:
            parsed, _ = ai_router.call_json(
                config,
                AIRequest(system=EVALUATION_SYSTEM, prompt=prompt, json_schema=EVALUATION_SCHEMA, max_tokens=4000),
                QuestionScore, context, extra_check=check,
            )
        except AIInvalidResponseError:
            # Rejected twice: never store unvalidated marks. The teacher marks this one.
            row.awarded = None
            row.flags = [FLAG_INVALID_OUTPUT]
            all_flags.add(FLAG_INVALID_OUTPUT)
            continue

        total = ZERO
        flags: list[str] = []
        by_id = {score.id: score for score in parsed.criteria}
        for index, (cid, criterion) in enumerate(ids.items(), start=1):
            score = by_id[cid]
            awarded = min(_marks(score.awarded), criterion.max_marks)
            evidence = [
                EvaluationEvidence(quote=quote.strip()[:2000], found_in_answer=evidence_found(quote, answer.text))
                for quote in score.evidence if quote.strip()
            ]
            if awarded > 0 and not any(e.found_in_answer for e in evidence):
                flags.append(FLAG_NO_EVIDENCE)
            row.criteria.append(EvaluationCriterion(
                rubric_criterion_id=criterion.id, position=index, name=criterion.name,
                max_marks=criterion.max_marks, awarded=awarded, explanation=score.explanation.strip() or None,
                missing_concepts=[m.strip() for m in score.missing_concepts if m.strip()], evidence=evidence,
            ))
            total += awarded

        if total > question.marks:  # impossible once every criterion is within its maximum
            raise AssertionError("Question total exceeds its maximum")
        row.awarded = total
        row.feedback = parsed.feedback.strip() or None
        row.missing_concepts = [m.strip() for m in parsed.missing_concepts if m.strip()]
        row.flags = sorted(set(flags))
        all_flags.update(row.flags)

    graded = [q.awarded for q in evaluation.questions]
    if any(value is None for value in graded):
        evaluation.total_awarded = None
        all_flags.add(FLAG_INCOMPLETE)
    else:
        evaluation.total_awarded = sum(graded, ZERO)  # type: ignore[arg-type]
        assert evaluation.total_awarded <= exam.total_marks
    evaluation.flags = sorted(all_flags)
    evaluation.completed_at = utcnow()

    db.execute(update(Evaluation).where(Evaluation.submission_id == submission.id).values(is_current=False))
    evaluation.is_current = True
    db.add(evaluation)
    return evaluation
