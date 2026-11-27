"""AI help while setting up an exam. Everything produced here is saved as an
unapproved draft for the teacher to review; nothing is approved automatically."""

import uuid
from decimal import Decimal

from fastapi import APIRouter

from app.api.deps import Client, DbSession, TeacherUser
from app.core.errors import AppError
from app.database.base import utcnow
from app.models.ai import ModelSlot
from app.models.exam import AnswerSource, DocumentKind, ExtractionStatus, QuestionType, Rubric, RubricCriterion
from app.providers.base import AIError, AIRequest
from app.schemas.exam import ExamDetail
from app.services import ai_router, audit, image_prep, storage
from app.services import exam_service as svc
from app.services.prompts import (
    DRAFT_ANSWER_SCHEMA,
    DRAFT_ANSWER_SYSTEM,
    PAPER_OCR_SYSTEM,
    PAPER_TEXT_SCHEMA,
    SUGGEST_RUBRIC_SYSTEM,
    SUGGESTED_RUBRIC_SCHEMA,
    DraftAnswer,
    PaperText,
    SuggestedRubric,
    draft_answer_prompt,
    suggest_rubric_prompt,
)

router = APIRouter(tags=["ai assist"])

MAX_PAPER_PAGES = 12


def _ai_failure(exc: AIError) -> AppError:
    return AppError(409 if exc.code == "not_configured" else 502, exc.message)


@router.post("/exams/{exam_id}/ocr-question-paper", response_model=ExamDetail)
def read_paper_with_ai(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> ExamDetail:
    """Transcribe a scanned or photographed question paper with the OCR model."""
    exam = svc.get_owned_exam(db, teacher, exam_id, full=True)
    svc.ensure_editable(exam)
    document = svc.latest_document(exam, DocumentKind.QUESTION_PAPER.value)
    if document is None:
        raise AppError(400, "Upload a question paper first")
    if document.extraction_status == ExtractionStatus.SUCCEEDED.value:
        raise AppError(409, "Text was already read from this paper")

    data = storage.path_for(document.storage_key).read_bytes()
    if document.content_type == "application/pdf":
        pages = image_prep.render_pdf(data)
    else:
        pages = [image_prep.PageImage(1, image_prep.enhance(data))]
    if len(pages) > MAX_PAPER_PAGES:
        raise AppError(413, f"Papers longer than {MAX_PAPER_PAGES} pages cannot be read with AI in one go")

    try:
        result, response = ai_router.run_json(
            db, teacher, ModelSlot.OCR,
            AIRequest(system=PAPER_OCR_SYSTEM, prompt="Transcribe this question paper.",
                      images=[p.image for p in pages], json_schema=PAPER_TEXT_SCHEMA, max_tokens=8000),
            PaperText, ai_router.TaskContext(task="read_question_paper", exam_id=exam.id),
        )
    except AIError as exc:
        raise _ai_failure(exc) from None

    if not result.text.strip():
        raise AppError(422, "The model could not read any text from the paper")
    document.extracted_text = result.text.strip()
    document.extraction_status = ExtractionStatus.SUCCEEDED.value
    document.extraction_message = f"Read by an AI model ({response.model}). Check the text against the paper."
    audit.record(db, "exam.paper_ocr", actor=teacher, entity_type="exam", entity_id=exam.id,
                 details={"title": exam.title}, ip_address=client.ip_address)
    db.commit()
    return svc.detail(db, exam.id)


def _leaf(db, teacher, question_id: uuid.UUID):
    question = svc.get_owned_question(db, teacher, question_id)
    svc.ensure_editable(question.exam)
    if question.children:
        raise AppError(422, "Model answers and rubrics belong to the sub-questions of this question")
    return question


def _full_question_text(question) -> str:
    if question.parent is not None and question.parent.text.strip():
        return f"{question.parent.text.strip()}\n{question.text}"
    return question.text


@router.post("/questions/{question_id}/model-answer/generate", response_model=ExamDetail)
def draft_model_answer(question_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> ExamDetail:
    question = _leaf(db, teacher, question_id)
    if not question.text.strip():
        raise AppError(422, "Add the question text first")
    if question.model_answer is not None and question.model_answer.is_approved:
        raise AppError(409, "This question already has an approved model answer. Remove or edit it instead.")
    try:
        result, _ = ai_router.run_json(
            db, teacher, ModelSlot.EVALUATOR,
            AIRequest(
                system=DRAFT_ANSWER_SYSTEM,
                prompt=draft_answer_prompt(_full_question_text(question),
                                           svc.fmt(question.marks) if question.marks else None,
                                           QuestionType(question.question_type).value.replace("_", " ")),
                json_schema=DRAFT_ANSWER_SCHEMA, max_tokens=3000,
            ),
            DraftAnswer, ai_router.TaskContext(task="draft_model_answer", exam_id=question.exam_id),
        )
    except AIError as exc:
        raise _ai_failure(exc) from None
    if not result.answer.strip():
        raise AppError(502, "The model returned an empty answer")
    svc.set_model_answer(question, result.answer.strip(), AnswerSource.AI_GENERATED.value, approved=False)
    audit.record(db, "question.ai_answer", actor=teacher, entity_type="question", entity_id=question.id,
                 details={"title": question.exam.title}, ip_address=client.ip_address)
    db.commit()
    return svc.detail(db, question.exam_id)


@router.post("/questions/{question_id}/rubric/suggest", response_model=ExamDetail)
def suggest_rubric(question_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> ExamDetail:
    question = _leaf(db, teacher, question_id)
    if question.marks is None:
        raise AppError(422, "Assign marks to this question first")
    if question.rubric is not None and question.rubric.is_approved:
        raise AppError(409, "This question already has an approved rubric. Edit it instead.")
    marks = question.marks

    def check(parsed: SuggestedRubric) -> None:
        if not parsed.criteria:
            raise ValueError("Return at least one criterion")
        if any(c.max_marks <= 0 or not c.name.strip() for c in parsed.criteria):
            raise ValueError("Every criterion needs a name and positive marks")
        total = sum((Decimal(str(c.max_marks)) for c in parsed.criteria), Decimal("0"))
        if total != marks:
            raise ValueError(f"The criteria add up to {svc.fmt(total)}, but must add up to exactly {svc.fmt(marks)}")

    try:
        result, _ = ai_router.run_json(
            db, teacher, ModelSlot.EVALUATOR,
            AIRequest(
                system=SUGGEST_RUBRIC_SYSTEM,
                prompt=suggest_rubric_prompt(
                    _full_question_text(question), svc.fmt(marks),
                    QuestionType(question.question_type).value.replace("_", " "),
                    question.model_answer.content if question.model_answer else None,
                ),
                json_schema=SUGGESTED_RUBRIC_SCHEMA, max_tokens=2000,
            ),
            SuggestedRubric, ai_router.TaskContext(task="suggest_rubric", exam_id=question.exam_id),
            extra_check=check,
        )
    except AIError as exc:
        raise _ai_failure(exc) from None

    rubric = question.rubric
    if rubric is None:
        rubric = Rubric(question_id=question.id)
        question.rubric = rubric
    rubric.criteria.clear()
    db.flush()
    for position, criterion in enumerate(result.criteria[:30], start=1):
        rubric.criteria.append(RubricCriterion(
            position=position, name=criterion.name.strip()[:200],
            description=criterion.description.strip()[:2000] or None,
            max_marks=Decimal(str(criterion.max_marks)).quantize(Decimal("0.01")),
        ))
    rubric.is_approved = False
    rubric.approved_at = None
    rubric.updated_at = utcnow()
    audit.record(db, "question.ai_rubric", actor=teacher, entity_type="question", entity_id=question.id,
                 details={"title": question.exam.title}, ip_address=client.ip_address)
    db.commit()
    return svc.detail(db, question.exam_id)
