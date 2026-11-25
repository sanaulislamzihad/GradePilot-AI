import io
from datetime import UTC, datetime, timedelta

import docx
import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.conftest import auth, register

FUTURE = (datetime.now(UTC) + timedelta(days=7)).isoformat()

PAPER_TEXT = [
    "CSE445 Midterm",
    "Q1. Explain Machine Learning. [5]",
    "Q2. Explain supervised and unsupervised learning.",
    "(a) Define supervised learning. (4 marks)",
    "(b) Compare it with unsupervised learning. [6]",
]


def make_pdf(lines: list[str]) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + index * 18), line)
    return document.tobytes()


def make_docx(lines: list[str]) -> bytes:
    document = docx.Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def create_exam(client: TestClient, teacher: dict, **overrides) -> dict:
    payload = {"title": "CSE445 Midterm", "exam_type": "midterm", "total_marks": 15,
               "submission_deadline": FUTURE, **overrides}
    response = client.post("/api/exams", headers=auth(teacher), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def leaf_by_label(exam: dict) -> dict[str, dict]:
    result = {}
    for q in exam["questions"]:
        if q["children"]:
            for c in q["children"]:
                result[c["full_label"]] = c
        else:
            result[q["full_label"]] = q
    return result


def check(exam: dict, key: str) -> dict:
    return next(c for c in exam["readiness"]["checks"] if c["key"] == key)


def upload(client, teacher, exam_id, filename, data, path="upload-question-paper", **params):
    return client.post(f"/api/exams/{exam_id}/{path}", headers=auth(teacher), params=params,
                       files={"file": (filename, data, "application/octet-stream")})


def build_ready_exam(client: TestClient, teacher: dict, **overrides) -> dict:
    exam = create_exam(client, teacher, **overrides)
    upload(client, teacher, exam["id"], "paper.pdf", make_pdf(PAPER_TEXT))
    exam = client.post(f"/api/exams/{exam['id']}/extract-questions", headers=auth(teacher), json={}).json()["exam"]
    for label, leaf in leaf_by_label(exam).items():
        client.put(f"/api/questions/{leaf['id']}/model-answer", headers=auth(teacher),
                   json={"content": f"Model answer for {label}", "approved": True})
        client.put(f"/api/questions/{leaf['id']}/rubric", headers=auth(teacher),
                   json={"approved": True, "criteria": [{"name": "Correctness", "max_marks": leaf["marks"]}]})
    return client.get(f"/api/exams/{exam['id']}", headers=auth(teacher)).json()


# --- Exam details ----------------------------------------------------------

def test_create_exam_normalises_formats_and_validates(client: TestClient, teacher):
    exam = create_exam(client, teacher, allowed_formats=["PDF", ".jpg"])
    assert exam["status"] == "draft"
    assert exam["allowed_formats"] == ["jpeg", "jpg", "pdf"]
    assert exam["total_marks"] == 15.0

    bad = [
        {"total_marks": 0},
        {"total_marks": 10.125},
        {"allowed_formats": ["exe"]},
        {"submission_deadline": "2030-01-01T10:00:00"},  # no timezone
        {"max_file_size_mb": 500},
    ]
    for override in bad:
        payload = {"title": "Bad exam", "total_marks": 10, **override}
        assert client.post("/api/exams", headers=auth(teacher), json=payload).status_code == 422, override


def test_course_and_section_must_belong_to_teacher(client: TestClient, teacher, make_client):
    course = client.post("/api/courses", headers=auth(teacher), json={"code": "CSE445", "name": "ML"}).json()
    section = client.post(f"/api/courses/{course['id']}/sections", headers=auth(teacher), json={"name": "1"}).json()
    exam = create_exam(client, teacher, course_id=course["id"], section_id=section["id"])
    assert exam["course_code"] == "CSE445" and exam["section_name"] == "1"

    other = register(make_client(), "teacher")
    response = client.post("/api/exams", headers=auth(other),
                           json={"title": "Steal", "total_marks": 5, "course_id": course["id"]})
    assert response.status_code == 422
    other_course = client.post("/api/courses", headers=auth(other), json={"code": "X1", "name": "Other course"}).json()
    response = client.post("/api/exams", headers=auth(other), json={
        "title": "Mismatch", "total_marks": 5, "course_id": other_course["id"], "section_id": section["id"]})
    assert response.status_code == 422


def test_exam_list_search_and_isolation(client: TestClient, teacher, make_client):
    create_exam(client, teacher, title="Quiz one", exam_type="quiz")
    create_exam(client, teacher, title="Final exam", exam_type="final")
    other = register(make_client(), "teacher")
    create_exam(client, other, title="Someone else")

    listing = client.get("/api/exams", headers=auth(teacher)).json()
    assert listing["total"] == 2
    assert client.get("/api/exams", headers=auth(teacher), params={"q": "final"}).json()["total"] == 1
    assert client.get("/api/exams", headers=auth(teacher), params={"status": "published"}).json()["total"] == 0

    foreign = client.get("/api/exams", headers=auth(other)).json()["items"][0]
    assert client.get(f"/api/exams/{foreign['id']}", headers=auth(teacher)).status_code == 404


def test_students_cannot_use_exam_management(client: TestClient, student):
    assert client.get("/api/exams", headers=auth(student)).status_code == 403
    assert client.post("/api/exams", headers=auth(student), json={"title": "x", "total_marks": 1}).status_code == 403


# --- Question paper upload and extraction ----------------------------------

def test_pdf_upload_and_question_extraction(client: TestClient, teacher):
    exam = create_exam(client, teacher)
    response = upload(client, teacher, exam["id"], "paper.pdf", make_pdf(PAPER_TEXT))
    assert response.status_code == 201
    document = response.json()["documents"][0]
    assert document["kind"] == "question_paper" and document["extraction_status"] == "succeeded"
    assert "Explain Machine Learning" in document["extracted_text"]

    result = client.post(f"/api/exams/{exam['id']}/extract-questions", headers=auth(teacher), json={}).json()
    assert result["created"] == 4 and result["with_marks"] == 3  # Q1, Q2 and its two parts
    leaves = leaf_by_label(result["exam"])
    assert list(leaves) == ["1", "2(a)", "2(b)"]
    assert leaves["2(a)"]["marks"] == 4.0
    parent = result["exam"]["questions"][1]
    assert parent["is_leaf"] is False and parent["marks"] == 10.0
    assert check(result["exam"], "marks")["ok"] is True

    # Extracting again would overwrite edits, so it needs explicit confirmation.
    again = client.post(f"/api/exams/{exam['id']}/extract-questions", headers=auth(teacher), json={})
    assert again.status_code == 409
    replaced = client.post(f"/api/exams/{exam['id']}/extract-questions", headers=auth(teacher), json={"replace": True})
    assert replaced.status_code == 200 and replaced.json()["created"] == 4


def test_docx_upload_replaces_previous_paper(client: TestClient, teacher):
    exam = create_exam(client, teacher)
    upload(client, teacher, exam["id"], "paper.pdf", make_pdf(PAPER_TEXT))
    response = upload(client, teacher, exam["id"], "paper.docx", make_docx(PAPER_TEXT))
    assert response.status_code == 201
    documents = response.json()["documents"]
    assert len(documents) == 1 and documents[0]["original_filename"] == "paper.docx"
    result = client.post(f"/api/exams/{exam['id']}/extract-questions", headers=auth(teacher), json={})
    assert result.json()["created"] == 4


def test_image_upload_is_stored_but_needs_ocr(client: TestClient, teacher):
    exam = create_exam(client, teacher)
    response = upload(client, teacher, exam["id"], "scan.png", make_png())
    assert response.status_code == 201
    assert response.json()["documents"][0]["extraction_status"] == "needs_ocr"
    extract = client.post(f"/api/exams/{exam['id']}/extract-questions", headers=auth(teacher), json={})
    assert extract.status_code == 422


def test_scanned_pdf_without_text_needs_ocr(client: TestClient, teacher):
    exam = create_exam(client, teacher)
    blank = pymupdf.open()
    blank.new_page()
    response = upload(client, teacher, exam["id"], "scan.pdf", blank.tobytes())
    assert response.json()["documents"][0]["extraction_status"] == "needs_ocr"


@pytest.mark.parametrize(
    ("filename", "data", "status"),
    [
        ("paper.pdf", b"this is not a pdf at all", 415),     # content does not match extension
        ("paper.exe", b"MZ\x90\x00", 415),                    # extension not allowed
        ("paper.png", make_pdf(["Q1. hi"]), 415),             # PDF renamed to .png
        ("paper.pdf", b"", 400),                              # empty
        ("broken.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50, 400),  # corrupt image
    ],
)
def test_upload_rejects_unsafe_files(client: TestClient, teacher, filename, data, status):
    exam = create_exam(client, teacher)
    assert upload(client, teacher, exam["id"], filename, data).status_code == status


def test_upload_size_limit(client: TestClient, teacher, monkeypatch):
    monkeypatch.setattr("app.api.routes.exams.DOCUMENT_MAX_BYTES", 1024)
    exam = create_exam(client, teacher)
    response = upload(client, teacher, exam["id"], "big.pdf", b"%PDF-" + b"0" * 4096)
    assert response.status_code == 413


def test_document_download_is_owner_only(client: TestClient, teacher, student, make_client):
    exam = create_exam(client, teacher)
    pdf = make_pdf(PAPER_TEXT)
    document = upload(client, teacher, exam["id"], "paper.pdf", pdf).json()["documents"][0]
    url = f"/api/exams/{exam['id']}/documents/{document['id']}"

    response = client.get(url, headers=auth(teacher))
    assert response.status_code == 200 and response.content == pdf
    assert "attachment" in response.headers["content-disposition"]

    other = register(make_client(), "teacher")
    assert client.get(url, headers=auth(other)).status_code == 404
    assert client.get(url, headers=auth(student)).status_code == 403
    assert client.get(url).status_code == 401


# --- Questions and marks ---------------------------------------------------

def test_manual_question_editing(client: TestClient, teacher):
    exam = create_exam(client, teacher, total_marks=10)
    base = f"/api/exams/{exam['id']}/questions"
    exam = client.post(base, headers=auth(teacher), json={"text": "Define AI", "marks": 4}).json()
    exam = client.post(base, headers=auth(teacher), json={"text": "Explain search"}).json()
    q1, q2 = exam["questions"]
    assert (q1["label"], q2["label"]) == ("1", "2")

    # Give question 1 a model answer, then sub-questions: it stops being gradable itself.
    client.put(f"/api/questions/{q1['id']}/model-answer", headers=auth(teacher), json={"content": "AI is..."})
    exam = client.post(base, headers=auth(teacher), json={"parent_id": q1["id"], "text": "Part a", "marks": 3}).json()
    exam = client.post(base, headers=auth(teacher), json={"parent_id": q1["id"], "text": "Part b", "marks": 2}).json()
    q1 = exam["questions"][0]
    assert [c["full_label"] for c in q1["children"]] == ["1(a)", "1(b)"]
    assert q1["marks"] == 5.0 and q1["model_answer"] is None

    assert client.post(base, headers=auth(teacher), json={"label": "2", "text": "dup"}).status_code == 409
    nested = client.post(base, headers=auth(teacher), json={"parent_id": q1["children"][0]["id"], "text": "deep"})
    assert nested.status_code == 422
    parent_marks = client.patch(f"/api/questions/{q1['id']}", headers=auth(teacher), json={"marks": 9})
    assert parent_marks.status_code == 422

    exam = client.post(f"{base}/reorder", headers=auth(teacher),
                       json={"ordered_ids": [q2["id"], q1["id"]]}).json()
    assert [q["label"] for q in exam["questions"]] == ["2", "1"]
    bad_order = client.post(f"{base}/reorder", headers=auth(teacher), json={"ordered_ids": [q2["id"]]})
    assert bad_order.status_code == 422

    exam = client.patch(f"/api/questions/{q2['id']}", headers=auth(teacher),
                        json={"text": "Explain informed search", "question_type": "descriptive", "marks": 5}).json()
    assert check(exam, "marks")["ok"] is True

    exam = client.delete(f"/api/questions/{q1['id']}", headers=auth(teacher)).json()
    assert [q["label"] for q in exam["questions"]] == ["2"]


def test_bulk_marks_and_total_validation(client: TestClient, teacher):
    exam = create_exam(client, teacher, total_marks=10)
    base = f"/api/exams/{exam['id']}/questions"
    client.post(base, headers=auth(teacher), json={"text": "One"})
    exam = client.post(base, headers=auth(teacher), json={"text": "Two"}).json()
    q1, q2 = exam["questions"]

    exam = client.put(f"/api/exams/{exam['id']}/marks", headers=auth(teacher), json={"items": [
        {"question_id": q1["id"], "marks": 4}, {"question_id": q2["id"], "marks": 4.5}]}).json()
    marks = check(exam, "marks")
    assert marks["ok"] is False and "Allocated 8.5 of 10" in marks["detail"]

    exam = client.put(f"/api/exams/{exam['id']}/marks", headers=auth(teacher), json={"items": [
        {"question_id": q2["id"], "marks": 6}]}).json()
    assert check(exam, "marks")["ok"] is True and exam["readiness"]["allocated_marks"] == 10.0


# --- Model answers and rubrics --------------------------------------------

def test_model_answer_approval_resets_on_edit(client: TestClient, teacher):
    exam = create_exam(client, teacher, total_marks=5)
    exam = client.post(f"/api/exams/{exam['id']}/questions", headers=auth(teacher), json={"text": "Q", "marks": 5}).json()
    qid = exam["questions"][0]["id"]

    exam = client.put(f"/api/questions/{qid}/model-answer", headers=auth(teacher),
                      json={"content": "Answer", "approved": True}).json()
    assert exam["questions"][0]["model_answer"]["is_approved"] is True
    assert check(exam, "model_answers")["ok"] is True

    exam = client.put(f"/api/questions/{qid}/model-answer", headers=auth(teacher),
                      json={"content": "Changed answer"}).json()
    assert exam["questions"][0]["model_answer"]["is_approved"] is False
    assert check(exam, "model_answers")["ok"] is False


def test_model_answer_upload_maps_answers_to_questions(client: TestClient, teacher):
    exam = create_exam(client, teacher)
    upload(client, teacher, exam["id"], "paper.pdf", make_pdf(PAPER_TEXT))
    exam = client.post(f"/api/exams/{exam['id']}/extract-questions", headers=auth(teacher), json={}).json()["exam"]
    leaves = leaf_by_label(exam)
    client.put(f"/api/questions/{leaves['1']['id']}/model-answer", headers=auth(teacher),
               json={"content": "Teacher approved answer", "approved": True})

    answers = make_docx(["1. ML lets computers learn from data.", "2(a) Learning from labelled data.",
                         "3. An answer for a question that does not exist."])
    response = upload(client, teacher, exam["id"], "answers.docx", answers, path="model-answer")
    assert response.status_code == 201
    result = response.json()
    assert result["matched"] == ["2(a)"]
    assert result["skipped_approved"] == ["1"]
    assert result["unmatched_questions"] == ["2(b)"]
    assert result["unused_sections"] == ["3"]

    leaves = leaf_by_label(result["exam"])
    assert leaves["2(a)"]["model_answer"] == {**leaves["2(a)"]["model_answer"], "source": "uploaded", "is_approved": False}
    assert leaves["1"]["model_answer"]["content"] == "Teacher approved answer"


def test_rubric_total_must_match_question_marks(client: TestClient, teacher):
    exam = create_exam(client, teacher, total_marks=5)
    exam = client.post(f"/api/exams/{exam['id']}/questions", headers=auth(teacher), json={"text": "Q", "marks": 5}).json()
    qid = exam["questions"][0]["id"]
    criteria = [{"name": "Definition", "max_marks": 2}, {"name": "Example", "max_marks": 1}]

    rejected = client.put(f"/api/questions/{qid}/rubric", headers=auth(teacher), json={"criteria": criteria, "approved": True})
    assert rejected.status_code == 422 and "add up to 3" in rejected.json()["detail"]

    draft = client.put(f"/api/questions/{qid}/rubric", headers=auth(teacher), json={"criteria": criteria}).json()
    assert draft["questions"][0]["rubric"]["total"] == 3.0

    criteria.append({"name": "Learning from data", "description": "Mentions data", "max_marks": 2})
    exam = client.put(f"/api/questions/{qid}/rubric", headers=auth(teacher), json={"criteria": criteria, "approved": True}).json()
    rubric = exam["questions"][0]["rubric"]
    assert rubric["is_approved"] is True and [c["name"] for c in rubric["criteria"]][-1] == "Learning from data"
    assert check(exam, "rubrics")["ok"] is True

    # Changing the question's marks invalidates the approved rubric for publishing.
    client.put(f"/api/exams/{exam['id']}/marks", headers=auth(teacher), json={"items": [{"question_id": qid, "marks": 4}]})
    exam = client.get(f"/api/exams/{exam['id']}", headers=auth(teacher)).json()
    assert check(exam, "rubrics")["ok"] is False and "differs" in check(exam, "rubrics")["detail"]


# --- Publication -----------------------------------------------------------

def test_publish_requires_readiness(client: TestClient, teacher):
    exam = create_exam(client, teacher)
    response = client.post(f"/api/exams/{exam['id']}/publish", headers=auth(teacher))
    assert response.status_code == 422 and "Questions" in response.json()["detail"]


def test_publish_lock_public_link_and_unpublish(client: TestClient, teacher):
    exam = build_ready_exam(client, teacher)
    assert exam["readiness"]["ready"] is True, exam["readiness"]

    published = client.post(f"/api/exams/{exam['id']}/publish", headers=auth(teacher)).json()
    assert published["status"] == "published" and published["public_slug"]
    slug = published["public_slug"]

    # Published exams are locked against edits.
    leaf = leaf_by_label(published)["1"]
    assert client.patch(f"/api/questions/{leaf['id']}", headers=auth(teacher), json={"text": "x"}).status_code == 409
    assert client.put(f"/api/exams/{exam['id']}", headers=auth(teacher),
                      json={"title": "New", "total_marks": 15}).status_code == 409
    assert client.delete(f"/api/exams/{exam['id']}", headers=auth(teacher)).status_code == 409

    public = client.get(f"/api/public/exams/{slug}")
    assert public.status_code == 200
    body = public.json()
    assert body["title"] == "CSE445 Midterm" and body["question_count"] == 3 and body["is_open"] is True
    assert "questions" not in body and "model_answer" not in str(body)

    client.post(f"/api/exams/{exam['id']}/unpublish", headers=auth(teacher))
    assert client.get(f"/api/public/exams/{slug}").status_code == 404
    republished = client.post(f"/api/exams/{exam['id']}/publish", headers=auth(teacher)).json()
    assert republished["public_slug"] == slug


def test_unknown_public_link_is_404(client: TestClient):
    assert client.get("/api/public/exams/does-not-exist").status_code == 404


def test_past_deadline_blocks_publishing(client: TestClient, teacher):
    exam = build_ready_exam(client, teacher)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    client.put(f"/api/exams/{exam['id']}", headers=auth(teacher),
               json={"title": exam["title"], "total_marks": 15, "submission_deadline": past})
    response = client.post(f"/api/exams/{exam['id']}/publish", headers=auth(teacher))
    assert response.status_code == 422 and "deadline has passed" in response.json()["detail"]


def test_deleting_exam_removes_stored_files(client: TestClient, teacher):
    from app.services import storage

    exam = create_exam(client, teacher)
    upload(client, teacher, exam["id"], "paper.pdf", make_pdf(PAPER_TEXT))
    from app.database.session import SessionLocal
    from app.models.exam import ExamDocument

    with SessionLocal() as db:
        key = db.query(ExamDocument).one().storage_key
    assert storage.path_for(key).is_file()
    assert client.delete(f"/api/exams/{exam['id']}", headers=auth(teacher)).status_code == 204
    with pytest.raises(FileNotFoundError):
        storage.path_for(key)
