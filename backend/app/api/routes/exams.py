"""Teacher exam management: details, question paper, questions, marks,
model answers, rubrics and publication."""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, File, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import Client, DbSession, TeacherUser
from app.core.errors import AppError
from app.database.base import utcnow
from app.models.exam import (
    AnswerSource,
    DocumentKind,
    Exam,
    ExamDocument,
    ExamStatus,
    ExtractionStatus,
    Question,
    Rubric,
    RubricCriterion,
)
from app.schemas.common import Page
from app.schemas.exam import (
    ExamCreate,
    ExamDetail,
    ExamSummary,
    ExamUpdate,
    ExtractQuestionsRequest,
    ExtractQuestionsResult,
    MarksUpdate,
    ModelAnswerUpdate,
    ModelAnswerUploadResult,
    QuestionCreate,
    QuestionUpdate,
    ReorderRequest,
    RubricUpdate,
)
from app.services import audit, storage
from app.services import exam_service as svc
from app.services.document_text import extract_text
from app.services.question_parser import flatten_answers, parse_parts
from app.services.uploads import read_validated

router = APIRouter(tags=["exams"])

DOCUMENT_FORMATS = {"pdf", "docx", "jpg", "jpeg", "png"}
DOCUMENT_MAX_BYTES = 20 * 1024 * 1024


def _record(db, teacher, action: str, exam: Exam, client, **details) -> None:
    audit.record(db, action, actor=teacher, entity_type="exam", entity_id=exam.id,
                 details={"title": exam.title, **details}, ip_address=client.ip_address)


# --- Exams -----------------------------------------------------------------

@router.get("/exams", response_model=Page[ExamSummary])
def list_exams(
    teacher: TeacherUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[ExamStatus | None, Query(alias="status")] = None,
    course_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ExamSummary]:
    query = select(Exam).where(Exam.teacher_id == teacher.id)
    if q and q.strip():
        query = query.where(Exam.title.ilike(f"%{q.strip()}%"))
    if status_filter:
        query = query.where(Exam.status == status_filter.value)
    if course_id:
        query = query.where(Exam.course_id == course_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    exams = db.scalars(
        query.options(
            selectinload(Exam.course), selectinload(Exam.section),
            selectinload(Exam.questions).selectinload(Question.children),
        )
        .order_by(Exam.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(items=[svc.summary(e) for e in exams], total=total, page=page, page_size=page_size)


@router.post("/exams", response_model=ExamDetail, status_code=status.HTTP_201_CREATED)
def create_exam(data: ExamCreate, teacher: TeacherUser, db: DbSession, client: Client) -> ExamDetail:
    course_id, section_id = svc.resolve_course_and_section(db, teacher, data.course_id, data.section_id)
    exam = Exam(teacher_id=teacher.id, **data.model_dump(exclude={"course_id", "section_id", "exam_type"}),
                exam_type=data.exam_type.value, course_id=course_id, section_id=section_id,
                status=ExamStatus.DRAFT.value)
    db.add(exam)
    db.flush()
    _record(db, teacher, "exam.create", exam, client)
    db.commit()
    return svc.detail(db, exam.id)


@router.get("/exams/{exam_id}", response_model=ExamDetail)
def get_exam(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    svc.get_owned_exam(db, teacher, exam_id)
    return svc.detail(db, exam_id)


@router.put("/exams/{exam_id}", response_model=ExamDetail)
def update_exam(exam_id: uuid.UUID, data: ExamUpdate, teacher: TeacherUser, db: DbSession, client: Client) -> ExamDetail:
    exam = svc.get_owned_exam(db, teacher, exam_id)
    svc.ensure_editable(exam)
    exam.course_id, exam.section_id = svc.resolve_course_and_section(db, teacher, data.course_id, data.section_id)
    for field, value in data.model_dump(exclude={"course_id", "section_id", "exam_type"}).items():
        setattr(exam, field, value)
    exam.exam_type = data.exam_type.value
    _record(db, teacher, "exam.update", exam, client)
    db.commit()
    return svc.detail(db, exam.id)


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> Response:
    exam = svc.get_owned_exam(db, teacher, exam_id)
    svc.ensure_editable(exam)
    keys = [d.storage_key for d in exam.documents]
    _record(db, teacher, "exam.delete", exam, client)
    db.delete(exam)
    db.commit()
    for key in keys:
        storage.delete(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Documents -------------------------------------------------------------

async def _store_document(db, exam: Exam, teacher, file: UploadFile, kind: DocumentKind) -> ExamDocument:
    validated = await read_validated(file, DOCUMENT_FORMATS, DOCUMENT_MAX_BYTES)
    result = extract_text(validated.data, validated.kind)

    # One active document per kind: replacing a file removes the old one.
    old_keys = []
    for old in [d for d in exam.documents if d.kind == kind.value]:
        old_keys.append(old.storage_key)
        db.delete(old)

    key = storage.save(f"exams/{exam.id}", validated.extension, validated.data)
    document = ExamDocument(
        exam_id=exam.id,
        kind=kind.value,
        original_filename=validated.original_filename,
        storage_key=key,
        content_type=validated.kind.content_type,
        size_bytes=len(validated.data),
        sha256=validated.sha256,
        page_count=result.page_count,
        extraction_status=result.status.value,
        extraction_message=result.message,
        extracted_text=result.text,
        uploaded_by_id=teacher.id,
    )
    db.add(document)
    try:
        db.flush()
    except Exception:
        storage.delete(key)
        raise
    for old_key in old_keys:
        storage.delete(old_key)
    return document


@router.post("/exams/{exam_id}/upload-question-paper", response_model=ExamDetail, status_code=status.HTTP_201_CREATED)
async def upload_question_paper(
    exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client, file: UploadFile = File(...)
) -> ExamDetail:
    exam = svc.get_owned_exam(db, teacher, exam_id, full=True)
    svc.ensure_editable(exam)
    document = await _store_document(db, exam, teacher, file, DocumentKind.QUESTION_PAPER)
    _record(db, teacher, "exam.question_paper_upload", exam, client,
            file=document.original_filename, extraction=document.extraction_status)
    db.commit()
    return svc.detail(db, exam.id)


@router.get("/exams/{exam_id}/documents/{document_id}")
def download_document(exam_id: uuid.UUID, document_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> FileResponse:
    exam = svc.get_owned_exam(db, teacher, exam_id)
    document = db.get(ExamDocument, document_id)
    if document is None or document.exam_id != exam.id:
        raise AppError(404, "Document not found")
    try:
        path = storage.path_for(document.storage_key)
    except (FileNotFoundError, ValueError):
        raise AppError(404, "The stored file is missing") from None
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.original_filename,
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete("/exams/{exam_id}/documents/{document_id}", response_model=ExamDetail)
def delete_document(
    exam_id: uuid.UUID, document_id: uuid.UUID, teacher: TeacherUser, db: DbSession
) -> ExamDetail:
    exam = svc.get_owned_exam(db, teacher, exam_id)
    svc.ensure_editable(exam)
    document = db.get(ExamDocument, document_id)
    if document is None or document.exam_id != exam.id:
        raise AppError(404, "Document not found")
    key = document.storage_key
    db.delete(document)
    db.commit()
    storage.delete(key)
    return svc.detail(db, exam.id)


@router.post("/exams/{exam_id}/extract-questions", response_model=ExtractQuestionsResult)
def extract_questions(
    exam_id: uuid.UUID, data: ExtractQuestionsRequest, teacher: TeacherUser, db: DbSession, client: Client
) -> ExtractQuestionsResult:
    exam = svc.get_owned_exam(db, teacher, exam_id, full=True)
    svc.ensure_editable(exam)
    document = svc.latest_document(exam, DocumentKind.QUESTION_PAPER.value)
    if document is None:
        raise AppError(400, "Upload a question paper first")
    if document.extraction_status != ExtractionStatus.SUCCEEDED.value or not document.extracted_text:
        raise AppError(422, document.extraction_message or "No text could be read from the question paper")

    parts = parse_parts(document.extracted_text)
    if not parts:
        raise AppError(
            422,
            "No numbered questions were found in the extracted text. Add the questions manually "
            "or check that questions start with labels such as Q1, 1. or 1(a).",
        )
    existing = [q for q in exam.questions if q.parent_id is None]
    if existing and not data.replace:
        raise AppError(409, "This exam already has questions. Confirm replacing them to extract again.")
    for question in existing:
        db.delete(question)
    db.flush()

    created = with_marks = 0
    for position, part in enumerate(parts, start=1):
        question = Question(
            exam_id=exam.id, label=part.label, position=position, text=part.text,
            question_type=part.question_type.value, marks=None if part.children else part.marks,
        )
        db.add(question)
        db.flush()
        created += 1
        with_marks += 0 if part.children or part.marks is None else 1
        for child_position, child in enumerate(part.children, start=1):
            db.add(Question(
                exam_id=exam.id, parent_id=question.id, label=child.label, position=child_position,
                text=child.text, question_type=child.question_type.value, marks=child.marks,
            ))
            created += 1
            with_marks += 1 if child.marks is not None else 0

    _record(db, teacher, "exam.questions_extract", exam, client, questions=created)
    db.commit()
    return ExtractQuestionsResult(created=created, with_marks=with_marks, exam=svc.detail(db, exam.id))


# --- Questions -------------------------------------------------------------

@router.post("/exams/{exam_id}/questions", response_model=ExamDetail, status_code=status.HTTP_201_CREATED)
def create_question(exam_id: uuid.UUID, data: QuestionCreate, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    exam = svc.get_owned_exam(db, teacher, exam_id)
    svc.ensure_editable(exam)
    parent = None
    if data.parent_id:
        parent = db.get(Question, data.parent_id)
        if parent is None or parent.exam_id != exam.id:
            raise AppError(404, "Parent question not found")
        if parent.parent_id is not None:
            raise AppError(422, "Sub-questions cannot have their own sub-questions")

    label = data.label or svc.next_label(db, exam, parent)
    svc.ensure_unique_label(db, exam, parent.id if parent else None, label)
    if parent is not None and not parent.children:
        svc.make_parent(db, parent)
    db.add(Question(
        exam_id=exam.id, parent_id=parent.id if parent else None, label=label,
        position=svc.next_position(db, exam, parent.id if parent else None),
        text=data.text, question_type=data.question_type.value, marks=data.marks,
    ))
    db.commit()
    return svc.detail(db, exam.id)


@router.patch("/questions/{question_id}", response_model=ExamDetail)
def update_question(question_id: uuid.UUID, data: QuestionUpdate, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    question = svc.get_owned_question(db, teacher, question_id)
    svc.ensure_editable(question.exam)
    if data.label is not None and data.label != question.label:
        svc.ensure_unique_label(db, question.exam, question.parent_id, data.label, exclude_id=question.id)
        question.label = data.label
    if data.text is not None:
        question.text = data.text
    if data.question_type is not None:
        question.question_type = data.question_type.value
    if data.marks is not None or data.clear_marks:
        if question.children:
            raise AppError(422, "Marks are set on sub-questions; this question's marks are their sum")
        question.marks = None if data.clear_marks else data.marks
    db.commit()
    return svc.detail(db, question.exam_id)


@router.delete("/questions/{question_id}", response_model=ExamDetail)
def delete_question(question_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    question = svc.get_owned_question(db, teacher, question_id)
    svc.ensure_editable(question.exam)
    exam_id = question.exam_id
    db.delete(question)
    db.commit()
    return svc.detail(db, exam_id)


@router.post("/exams/{exam_id}/questions/reorder", response_model=ExamDetail)
def reorder_questions(exam_id: uuid.UUID, data: ReorderRequest, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    exam = svc.get_owned_exam(db, teacher, exam_id)
    svc.ensure_editable(exam)
    siblings = db.scalars(
        select(Question).where(Question.exam_id == exam.id, svc.sibling_filter(data.parent_id))
    ).all()
    if {q.id for q in siblings} != set(data.ordered_ids) or len(data.ordered_ids) != len(siblings):
        raise AppError(422, "The new order must list every question at this level exactly once")
    by_id = {q.id: q for q in siblings}
    for position, question_id in enumerate(data.ordered_ids, start=1):
        by_id[question_id].position = position
    db.commit()
    return svc.detail(db, exam.id)


@router.put("/exams/{exam_id}/marks", response_model=ExamDetail)
def update_marks(exam_id: uuid.UUID, data: MarksUpdate, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    exam = svc.get_owned_exam(db, teacher, exam_id, full=True)
    svc.ensure_editable(exam)
    leaf_ids = {q.id: q for q, _ in svc.leaves(exam)}
    for item in data.items:
        question = leaf_ids.get(item.question_id)
        if question is None:
            raise AppError(422, "Marks can only be set on gradable questions of this exam")
        question.marks = item.marks
    db.commit()
    return svc.detail(db, exam.id)


# --- Model answers ---------------------------------------------------------

def _owned_leaf(db, teacher, question_id: uuid.UUID) -> Question:
    question = svc.get_owned_question(db, teacher, question_id)
    svc.ensure_editable(question.exam)
    if question.children:
        raise AppError(422, "Model answers and rubrics belong to the sub-questions of this question")
    return question


@router.put("/questions/{question_id}/model-answer", response_model=ExamDetail)
def save_model_answer(question_id: uuid.UUID, data: ModelAnswerUpdate, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    question = _owned_leaf(db, teacher, question_id)
    source = question.model_answer.source if question.model_answer else AnswerSource.MANUAL.value
    if question.model_answer and question.model_answer.content != data.content:
        source = AnswerSource.MANUAL.value
    svc.set_model_answer(question, data.content, source, data.approved)
    db.commit()
    return svc.detail(db, question.exam_id)


@router.delete("/questions/{question_id}/model-answer", response_model=ExamDetail)
def delete_model_answer(question_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    question = _owned_leaf(db, teacher, question_id)
    if question.model_answer is not None:
        db.delete(question.model_answer)
        db.commit()
    return svc.detail(db, question.exam_id)


@router.post("/exams/{exam_id}/model-answer", response_model=ModelAnswerUploadResult, status_code=status.HTTP_201_CREATED)
async def upload_model_answer(
    exam_id: uuid.UUID,
    teacher: TeacherUser,
    db: DbSession,
    client: Client,
    file: UploadFile = File(...),
    overwrite_approved: bool = Query(default=False),
) -> ModelAnswerUploadResult:
    """Upload a model answer document and pre-fill answers for matching question labels.

    Pre-filled answers are saved unapproved; the teacher reviews each one.
    """
    exam = svc.get_owned_exam(db, teacher, exam_id, full=True)
    svc.ensure_editable(exam)
    document = await _store_document(db, exam, teacher, file, DocumentKind.MODEL_ANSWER)

    matched: list[str] = []
    skipped: list[str] = []
    unmatched: list[str] = []
    unused: list[str] = []
    if document.extraction_status == ExtractionStatus.SUCCEEDED.value and document.extracted_text:
        sections = flatten_answers(parse_parts(document.extracted_text))
        used: set[str] = set()
        for question, label in svc.leaves(exam):
            text = sections.get(label)
            if not text:
                unmatched.append(label)
                continue
            used.add(label)
            if question.model_answer and question.model_answer.is_approved and not overwrite_approved:
                skipped.append(label)
                continue
            svc.set_model_answer(question, text, AnswerSource.UPLOADED.value, approved=False)
            matched.append(label)
        unused = [label for label in sections if label not in used]
    else:
        unmatched = [label for _, label in svc.leaves(exam)]

    _record(db, teacher, "exam.model_answer_upload", exam, client,
            file=document.original_filename, matched=len(matched))
    db.commit()
    detail = svc.detail(db, exam.id)
    return ModelAnswerUploadResult(
        document=next(d for d in detail.documents if d.id == document.id),
        matched=matched, skipped_approved=skipped, unmatched_questions=unmatched,
        unused_sections=unused, exam=detail,
    )


# --- Rubrics ---------------------------------------------------------------

@router.put("/questions/{question_id}/rubric", response_model=ExamDetail)
def save_rubric(question_id: uuid.UUID, data: RubricUpdate, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    question = _owned_leaf(db, teacher, question_id)
    total = sum((c.max_marks for c in data.criteria), Decimal("0"))
    if data.approved:
        if question.marks is None:
            raise AppError(422, "Assign marks to this question before approving its rubric")
        if total != question.marks:
            raise AppError(
                422,
                f"Rubric criteria add up to {svc.fmt(total)} but the question is worth "
                f"{svc.fmt(question.marks)} marks",
            )

    rubric = question.rubric
    if rubric is None:
        rubric = Rubric(question_id=question.id)
        question.rubric = rubric
    rubric.criteria.clear()
    db.flush()
    for position, criterion in enumerate(data.criteria, start=1):
        rubric.criteria.append(RubricCriterion(
            position=position, name=criterion.name, description=criterion.description or None,
            max_marks=criterion.max_marks,
        ))
    rubric.is_approved = data.approved
    rubric.approved_at = utcnow() if data.approved else None
    db.commit()
    return svc.detail(db, question.exam_id)


@router.delete("/questions/{question_id}/rubric", response_model=ExamDetail)
def delete_rubric(question_id: uuid.UUID, teacher: TeacherUser, db: DbSession) -> ExamDetail:
    question = _owned_leaf(db, teacher, question_id)
    if question.rubric is not None:
        db.delete(question.rubric)
        db.commit()
    return svc.detail(db, question.exam_id)


# --- Publication -----------------------------------------------------------

@router.post("/exams/{exam_id}/publish", response_model=ExamDetail)
def publish_exam(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> ExamDetail:
    exam = svc.get_owned_exam(db, teacher, exam_id, full=True)
    if exam.status == ExamStatus.PUBLISHED.value:
        raise AppError(409, "This exam is already published")
    check = svc.readiness(exam)
    if not check.ready:
        failing = "; ".join(f"{c.label}: {c.detail}" for c in check.checks if not c.ok)
        raise AppError(422, f"The exam is not ready to publish. {failing}")
    exam.status = ExamStatus.PUBLISHED.value
    exam.published_at = utcnow()
    exam.public_slug = exam.public_slug or svc.generate_slug(db)
    _record(db, teacher, "exam.publish", exam, client)
    db.commit()
    return svc.detail(db, exam.id)


@router.post("/exams/{exam_id}/unpublish", response_model=ExamDetail)
def unpublish_exam(exam_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> ExamDetail:
    exam = svc.get_owned_exam(db, teacher, exam_id)
    if exam.status != ExamStatus.PUBLISHED.value:
        raise AppError(409, "This exam is not published")
    exam.status = ExamStatus.DRAFT.value
    _record(db, teacher, "exam.unpublish", exam, client)
    db.commit()
    return svc.detail(db, exam.id)

