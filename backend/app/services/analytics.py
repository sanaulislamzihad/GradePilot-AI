"""Exam analytics from real records.

Mark statistics use teacher-approved marks only (approved or published), so
unreviewed AI suggestions never shape the numbers a teacher reports.
"""

import re
import statistics
from collections import Counter
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.course import CourseSection, SectionEnrollment
from app.models.evaluation import Evaluation, EvaluationQuestion, FinalResult, ReviewStatus
from app.models.exam import Exam
from app.models.submission import Submission, SubmissionStatus as S
from app.schemas.results import ConceptCount, DistributionBucket, ExamAnalytics, QuestionStat
from app.services import review
from app.services.exam_service import leaves

FINAL_STATUSES = (S.APPROVED.value, S.PUBLISHED.value)


def approved_evaluations(db: Session, exam: Exam) -> list[tuple[Submission, Evaluation]]:
    rows = db.execute(
        select(Submission, Evaluation)
        .join(Evaluation, Evaluation.submission_id == Submission.id)
        .where(
            Submission.exam_id == exam.id, Submission.is_latest.is_(True), Evaluation.is_current.is_(True),
            Evaluation.review_status == ReviewStatus.APPROVED.value, Submission.status.in_(FINAL_STATUSES),
        )
        .options(selectinload(Evaluation.questions).selectinload(EvaluationQuestion.criteria), selectinload(Submission.student))
    ).all()
    return [(s, e) for s, e in rows if e.final_total is not None]


def _expected_students(db: Session, exam: Exam, submitters: int) -> int:
    if exam.course_id is None:
        return submitters
    query = select(func.count(func.distinct(SectionEnrollment.student_id))).join(
        CourseSection, SectionEnrollment.section_id == CourseSection.id
    )
    query = query.where(SectionEnrollment.section_id == exam.section_id) if exam.section_id else query.where(
        CourseSection.course_id == exam.course_id
    )
    return max(db.scalar(query) or 0, submitters)


def _concept_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower().rstrip("."))


def compute(db: Session, exam: Exam) -> ExamAnalytics:
    statuses = dict(db.execute(
        select(Submission.status, func.count(Submission.id))
        .where(Submission.exam_id == exam.id, Submission.is_latest.is_(True))
        .group_by(Submission.status)
    ).all())
    total_submissions = sum(statuses.values())
    published = db.scalar(select(func.count(FinalResult.id)).where(FinalResult.exam_id == exam.id)) or 0
    approved = statuses.get(S.APPROVED.value, 0)

    graded = approved_evaluations(db, exam)
    totals = [float(e.final_total) for _, e in graded]  # type: ignore[arg-type]
    total_marks = float(exam.total_marks)

    buckets = [0] * 10
    for value in totals:
        share = value / total_marks if total_marks else 0
        buckets[min(9, int(share * 10))] += 1
    distribution = [DistributionBucket(label=f"{i * 10}–{(i + 1) * 10}%", count=n) for i, n in enumerate(buckets)]

    per_question: dict = {}
    concepts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for _, evaluation in graded:
        for row in evaluation.questions:
            final = review.question_final(row)
            stat = per_question.setdefault(row.question_id, {"sum": Decimal("0"), "n": 0, "answered": 0})
            if final is not None:
                stat["sum"] += final
                stat["n"] += 1
            stat["answered"] += row.answer_status == "answered"
            for concept in [*row.missing_concepts, *[m for c in row.criteria for m in c.missing_concepts]]:
                key = _concept_key(concept)
                if key:
                    concepts[key] += 1
                    display.setdefault(key, concept.strip().rstrip("."))

    questions = []
    for question, label in leaves(exam):
        stat = per_question.get(question.id, {"sum": Decimal("0"), "n": 0, "answered": 0})
        maximum = float(question.marks or 0)
        average = float(stat["sum"] / stat["n"]) if stat["n"] else None
        questions.append(QuestionStat(
            label=label, text=question.text[:200], max_marks=maximum,
            average=round(average, 2) if average is not None else None,
            average_percentage=round(average / maximum * 100, 1) if average is not None and maximum else None,
            answered=stat["answered"],
        ))
    ranked = [q for q in questions if q.average_percentage is not None]
    weakest = sorted(ranked, key=lambda q: q.average_percentage)[:3]  # type: ignore[arg-type, return-value]

    average = statistics.fmean(totals) if totals else None
    return ExamAnalytics(
        exam_id=exam.id,
        exam_title=exam.title,
        total_marks=total_marks,
        total_students=_expected_students(db, exam, total_submissions),
        total_submissions=total_submissions,
        pending_evaluations=total_submissions - approved - statuses.get(S.PUBLISHED.value, 0),
        approved_results=approved,
        published_results=published,
        graded_count=len(totals),
        average=round(average, 2) if average is not None else None,
        median=round(statistics.median(totals), 2) if totals else None,
        highest=max(totals) if totals else None,
        lowest=min(totals) if totals else None,
        average_percentage=round(average / total_marks * 100, 1) if average is not None and total_marks else None,
        distribution=distribution,
        questions=questions,
        weakest_questions=weakest,
        common_missing_concepts=[ConceptCount(concept=display[k], count=n) for k, n in concepts.most_common(10)],
    )
