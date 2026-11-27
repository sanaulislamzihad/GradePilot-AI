"""Stage 1 and 2: read the script and split it into one answer per question.

Digital PDFs are read from their text layer and split with the local parser;
the AI model is used only when the text cannot be split by question labels.
Scans and photos are transcribed by the OCR (vision) model, a few pages at a time.
Anything uncertain is routed to the teacher instead of being guessed.
"""

import re
from collections import OrderedDict
from dataclasses import dataclass, field

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.ai import ModelSlot
from app.models.evaluation import AnswerStatus, ExtractedAnswer, ExtractionSource
from app.models.exam import Exam, Question
from app.models.submission import Submission
from app.providers.base import AIConfigurationError, AIRequest
from app.services import ai_router, image_prep, storage
from app.services.exam_service import leaves
from app.services.prompts import (
    EXTRACTION_SCHEMA,
    EXTRACTION_SYSTEM,
    ExtractionResult,
    extraction_prompt,
)
from app.services.question_parser import flatten_answers, parse_parts

PAGES_PER_REQUEST = 6
REVIEW_CONFIDENCE = 0.75


@dataclass
class _Answer:
    text: str = ""
    pages: list[int] = field(default_factory=list)
    confidence: float = 1.0
    unreadable: list[str] = field(default_factory=list)


@dataclass
class ExtractionOutcome:
    needs_review: bool
    notes: list[str]


def normalise_label(label: str) -> str:
    """'Q2a', '2 (a)', 'Question 2(a)' -> '2(a)' for matching against exam labels."""
    cleaned = re.sub(r"(?i)^\s*(q(uestion)?\.?\s*)", "", label.strip())
    match = re.match(r"^(\d+)\s*\(?\s*([a-z]{1,4})?\s*\)?\.?$", cleaned, re.IGNORECASE)
    if not match:
        return cleaned.lower()
    number, part = match.groups()
    return f"{number}({part.lower()})" if part else number


def _merge(results: list[ExtractionResult], labels: set[str]) -> tuple[dict[str, _Answer], list[str]]:
    merged: dict[str, _Answer] = OrderedDict()
    unassigned: list[str] = []
    for result in results:
        for part in result.answers:
            label = normalise_label(part.label)
            if label not in labels:
                if part.text.strip():
                    unassigned.append(f"[{part.label}] {part.text.strip()}")
                continue
            answer = merged.setdefault(label, _Answer(confidence=1.0))
            answer.text = f"{answer.text}\n{part.text.strip()}".strip()
            answer.pages = sorted(set(answer.pages) | set(part.pages))
            answer.confidence = min(answer.confidence, part.confidence)
            answer.unreadable.extend(part.unreadable)
        if result.unassigned_text.strip():
            unassigned.append(result.unassigned_text.strip())
    return merged, unassigned


def _document_slot(db: Session, teacher_id) -> ModelSlot:
    # Text-only splitting can use the evaluator when no OCR model is set up.
    return ModelSlot.OCR if ai_router.has_slot(db, teacher_id, ModelSlot.OCR) else ModelSlot.EVALUATOR


def _ai_extract(db: Session, submission: Submission, questions: list[tuple[str, str]], *,
                pages: list[image_prep.PageImage] | None = None, text: str | None = None,
                slot: ModelSlot) -> list[ExtractionResult]:
    context = ai_router.TaskContext(task="extract_answers", submission_id=submission.id, exam_id=submission.exam_id)
    teacher_id = submission.exam.teacher_id
    if text is not None:
        result, _ = ai_router.run_json(
            db, teacher_id, slot,
            AIRequest(system=EXTRACTION_SYSTEM, prompt=extraction_prompt(questions, None, text),
                      json_schema=EXTRACTION_SCHEMA, max_tokens=8000),
            ExtractionResult, context,
        )
        return [result]

    results = []
    assert pages is not None
    for start in range(0, len(pages), PAGES_PER_REQUEST):
        batch = pages[start:start + PAGES_PER_REQUEST]
        result, _ = ai_router.run_json(
            db, teacher_id, slot,
            AIRequest(
                system=EXTRACTION_SYSTEM,
                prompt=extraction_prompt(questions, [p.page for p in batch]),
                images=[p.image for p in batch],
                json_schema=EXTRACTION_SCHEMA,
                max_tokens=8000,
            ),
            ExtractionResult, context,
        )
        results.append(result)
    return results


def _page_of(text: str, page_texts: list[str]) -> list[int]:
    probe = " ".join(text.split())[:40]
    return [i + 1 for i, page in enumerate(page_texts) if probe and probe in " ".join(page.split())]


def extract(db: Session, submission: Submission) -> ExtractionOutcome:
    exam: Exam = submission.exam
    gradable: list[tuple[Question, str]] = list(leaves(exam))
    labels = {label for _, label in gradable}
    questions = [(label, question.text) for question, label in gradable]
    notes: list[str] = []
    files = submission.files

    answers: dict[str, _Answer]
    source: ExtractionSource
    unassigned: list[str] = []

    is_single_pdf = len(files) == 1 and files[0].content_type == "application/pdf"
    pdf_data = storage.path_for(files[0].storage_key).read_bytes() if is_single_pdf else None
    page_texts = image_prep.pdf_page_texts(pdf_data) if pdf_data is not None else []

    if pdf_data is not None and image_prep.pdf_has_text_layer(page_texts):
        source = ExtractionSource.PDF_TEXT
        full_text = "\n\n".join(page_texts)
        sections = flatten_answers(parse_parts(full_text))
        found = {normalise_label(label): text for label, text in sections.items()}
        if found and any(label in labels for label in found):
            answers = {label: _Answer(text=text, pages=_page_of(text, page_texts))
                       for label, text in found.items() if label in labels}
            extra = [label for label in found if label not in labels]
            if extra:
                unassigned.append(f"Sections labelled {', '.join(extra)} do not match any question.")
        else:
            # The text has no recognisable question labels: let the model split it.
            results = _ai_extract(db, submission, questions, text=full_text, slot=_document_slot(db, exam.teacher_id))
            answers, unassigned = _merge(results, labels)
            source = ExtractionSource.AI_OCR
    else:
        if not ai_router.has_slot(db, exam.teacher_id, ModelSlot.OCR):
            raise AIConfigurationError(
                "This script is scanned or photographed. Set up an OCR model (with image support) in AI Settings."
            )
        source = ExtractionSource.AI_OCR
        pages: list[image_prep.PageImage] = []
        for file in files:
            data = storage.path_for(file.storage_key).read_bytes()
            if file.content_type == "application/pdf":
                pages.extend(image_prep.render_pdf(data, first_page=len(pages) + 1))
            else:
                pages.append(image_prep.PageImage(len(pages) + 1, image_prep.enhance(data)))
        results = _ai_extract(db, submission, questions, pages=pages, slot=ModelSlot.OCR)
        answers, unassigned = _merge(results, labels)

    db.execute(delete(ExtractedAnswer).where(ExtractedAnswer.submission_id == submission.id))
    needs_review = False
    for question, label in gradable:
        answer = answers.get(label)
        if answer is None or not answer.text.strip():
            status = AnswerStatus.UNREADABLE if answer and answer.unreadable else AnswerStatus.MISSING
            flagged = status == AnswerStatus.UNREADABLE
            db.add(ExtractedAnswer(
                submission_id=submission.id, question_id=question.id, text="", status=status.value,
                source=source.value, confidence=answer.confidence if answer else 1.0,
                pages=answer.pages if answer else [], unreadable_notes=answer.unreadable if answer else [],
                needs_review=flagged,
            ))
            needs_review |= flagged
            continue
        flagged = answer.confidence < REVIEW_CONFIDENCE or bool(answer.unreadable)
        needs_review |= flagged
        db.add(ExtractedAnswer(
            submission_id=submission.id, question_id=question.id, text=answer.text.strip(),
            status=AnswerStatus.ANSWERED.value, source=source.value, confidence=answer.confidence,
            pages=answer.pages, unreadable_notes=answer.unreadable, needs_review=flagged,
        ))

    if unassigned:
        # Text that belongs to no question may be a mislabelled answer: a teacher should look.
        needs_review = True
        notes.append("Text not matched to any question:\n" + "\n".join(unassigned))
    missing = [label for _, label in gradable if label not in answers]
    if missing:
        notes.append(f"No answer found for question {', '.join(missing)}.")
    return ExtractionOutcome(needs_review=needs_review, notes=notes)
