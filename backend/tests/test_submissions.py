import io
import uuid
from datetime import UTC, datetime, timedelta

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import update

from app.database.session import SessionLocal
from app.models.exam import Exam
from tests.conftest import auth, register
from tests.test_exams import build_ready_exam, make_pdf


def published_exam(client: TestClient, teacher: dict, **overrides) -> dict:
    exam = build_ready_exam(client, teacher, **overrides)
    response = client.post(f"/api/exams/{exam['id']}/publish", headers=auth(teacher))
    assert response.status_code == 200, response.text
    return response.json()


def png(color: str = "white") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), color).save(buffer, format="PNG")
    return buffer.getvalue()


def submit(client: TestClient, student: dict, exam_id: str, files: list[tuple[str, bytes]], key: str | None = None):
    headers = auth(student) | ({"Idempotency-Key": key} if key else {})
    return client.post(
        f"/api/exams/{exam_id}/submissions",
        headers=headers,
        files=[("files", (name, data, "application/octet-stream")) for name, data in files],
    )


def script(text: str = "My answers") -> list[tuple[str, bytes]]:
    return [("answers.pdf", make_pdf([text, "Q1. Machine learning is ...", "Q2(a) Supervised ..."]))]


def expire_deadline(exam_id: str) -> None:
    with SessionLocal() as db:
        db.execute(update(Exam).where(Exam.id == uuid.UUID(exam_id)).values(
            submission_deadline=datetime.now(UTC) - timedelta(minutes=1)))
        db.commit()


# --- Happy path ------------------------------------------------------------

def test_student_submits_and_teacher_receives(client: TestClient, teacher, student):
    exam = published_exam(client, teacher)
    slug = exam["public_slug"]

    view = client.get(f"/api/student/exams/{slug}", headers=auth(student)).json()
    assert view["can_submit"] is True and view["attempts_left"] == 1 and view["blocked_reason"] is None
    assert view["question_count"] == 3 and "questions" not in view

    response = submit(client, student, exam["id"], script())
    assert response.status_code == 201, response.text
    submission = response.json()
    assert submission["code"].startswith("GP-") and len(submission["code"]) == 11
    assert submission["status"] == "uploaded" and submission["attempt_number"] == 1
    assert submission["student"]["student_number"] == student["user"]["student_id"]
    assert submission["file_count"] == 1 and submission["page_count"] == 1
    assert submission["files"][0]["content_type"] == "application/pdf"

    view = client.get(f"/api/student/exams/{slug}", headers=auth(student)).json()
    assert view["can_submit"] is False and view["blocked_reason"] == "You have already submitted this exam."
    assert view["latest_submission"]["code"] == submission["code"]

    listing = client.get("/api/submissions", headers=auth(teacher), params={"exam_id": exam["id"]}).json()
    assert listing["total"] == 1 and listing["items"][0]["code"] == submission["code"]

    file_url = f"/api/submissions/{submission['id']}/files/{submission['files'][0]['id']}"
    download = client.get(file_url, headers=auth(teacher))
    assert download.status_code == 200 and download.content.startswith(b"%PDF-")
    assert client.get(file_url, headers=auth(student)).status_code == 200

    detail = client.get(f"/api/exams/{exam['id']}", headers=auth(teacher)).json()
    assert detail["submission_count"] == 1


def test_image_pages_are_accepted_in_order(client: TestClient, teacher, student):
    exam = published_exam(client, teacher)
    pages = [("page-1.png", png("white")), ("page-2.png", png("gray")), ("page-3.jpg", b"")]
    jpeg = io.BytesIO()
    Image.new("RGB", (40, 40), "black").save(jpeg, format="JPEG")
    pages[2] = ("page-3.jpg", jpeg.getvalue())

    submission = submit(client, student, exam["id"], pages).json()
    assert submission["file_count"] == 3 and submission["page_count"] == 3
    assert [f["original_filename"] for f in submission["files"]] == ["page-1.png", "page-2.png", "page-3.jpg"]


def test_multi_page_pdf_page_count(client: TestClient, teacher, student):
    exam = published_exam(client, teacher)
    document = pymupdf.open()
    for i in range(4):
        document.new_page().insert_text((72, 72), f"Page {i + 1}")
    submission = submit(client, student, exam["id"], [("script.pdf", document.tobytes())]).json()
    assert submission["page_count"] == 4


# --- Attempts and duplicates -----------------------------------------------

def test_replacement_attempts_follow_the_policy(client: TestClient, teacher, student):
    exam = published_exam(client, teacher, max_attempts=2)
    first_files = script("first")
    first = submit(client, student, exam["id"], first_files).json()

    same = submit(client, student, exam["id"], first_files)
    assert same.status_code == 409 and "same files" in same.json()["detail"]

    second = submit(client, student, exam["id"], script("second"))
    assert second.status_code == 201 and second.json()["attempt_number"] == 2

    third = submit(client, student, exam["id"], script("third"))
    assert third.status_code == 409 and "all 2 submission attempts" in third.json()["detail"]

    latest = client.get("/api/submissions", headers=auth(student)).json()
    assert latest["total"] == 1 and latest["items"][0]["attempt_number"] == 2
    history = client.get("/api/submissions", headers=auth(student), params={"latest_only": False}).json()
    assert [s["attempt_number"] for s in history["items"]] == [2, 1]
    old = client.get(f"/api/submissions/{first['id']}", headers=auth(student)).json()
    assert old["is_latest"] is False


def test_repeated_request_with_same_key_creates_one_submission(client: TestClient, teacher, student):
    exam = published_exam(client, teacher, max_attempts=3)
    key = str(uuid.uuid4())
    first = submit(client, student, exam["id"], script("a"), key=key)
    again = submit(client, student, exam["id"], script("a"), key=key)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert client.get("/api/submissions", headers=auth(student), params={"latest_only": False}).json()["total"] == 1

    assert submit(client, student, exam["id"], script("b"), key="bad key!").status_code == 422


# --- File validation -------------------------------------------------------

@pytest.mark.parametrize(
    ("files", "status", "message"),
    [
        ([], 422, None),
        ([("a.pdf", make_pdf(["one"])), ("b.png", png())], 422, "one PDF"),
        ([("a.pdf", make_pdf(["one"])), ("b.pdf", make_pdf(["two"]))], 422, "one PDF"),
        ([("a.pdf", b"not really a pdf")], 415, None),
        ([("a.docx", b"PK\x03\x04")], 415, None),
        ([("a.pdf", b"%PDF-1.7 broken")], 400, "damaged"),
    ],
)
def test_invalid_scripts_are_rejected(client: TestClient, teacher, student, files, status, message):
    exam = published_exam(client, teacher)
    response = submit(client, student, exam["id"], files)
    assert response.status_code == status, response.text
    if message:
        assert message in response.json()["detail"]
    assert client.get("/api/submissions", headers=auth(student)).json()["total"] == 0


def test_exam_format_and_size_policy_is_enforced(client: TestClient, teacher, student):
    exam = published_exam(client, teacher, allowed_formats=["pdf"], max_file_size_mb=1, max_attempts=3)
    assert submit(client, student, exam["id"], [("page.png", png())]).status_code == 415
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    assert submit(client, student, exam["id"], [("big.pdf", big)]).status_code == 413


def test_encrypted_pdf_is_rejected(client: TestClient, teacher, student):
    exam = published_exam(client, teacher)
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "secret")
    locked = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    response = submit(client, student, exam["id"], [("locked.pdf", locked)])
    assert response.status_code == 400 and "password" in response.json()["detail"]


# --- Eligibility -----------------------------------------------------------

def test_deadline_is_enforced_on_the_server(client: TestClient, teacher, student):
    exam = published_exam(client, teacher)
    expire_deadline(exam["id"])
    response = submit(client, student, exam["id"], script())
    assert response.status_code == 409 and "deadline has passed" in response.json()["detail"]
    view = client.get(f"/api/student/exams/{exam['public_slug']}", headers=auth(student)).json()
    assert view["is_open"] is False and view["can_submit"] is False


def test_course_exams_are_limited_to_enrolled_students(client: TestClient, teacher, student, make_client):
    course = client.post("/api/courses", headers=auth(teacher), json={"code": "CSE445", "name": "ML"}).json()
    section = client.post(f"/api/courses/{course['id']}/sections", headers=auth(teacher), json={"name": "1"}).json()
    exam = published_exam(client, teacher, course_id=course["id"], section_id=section["id"])
    slug = exam["public_slug"]

    outsider_view = client.get(f"/api/student/exams/{slug}", headers=auth(student)).json()
    assert outsider_view["can_submit"] is False and "CSE445 Section 1" in outsider_view["blocked_reason"]
    assert submit(client, student, exam["id"], script()).status_code == 403
    assert client.get("/api/student/exams", headers=auth(student)).json() == []

    client.post("/api/student/enrollments", headers=auth(student), json={"join_code": section["join_code"]})
    available = client.get("/api/student/exams", headers=auth(student)).json()
    assert [e["title"] for e in available] == ["CSE445 Midterm"] and available[0]["latest_submission"] is None
    assert submit(client, student, exam["id"], script()).status_code == 201
    assert client.get("/api/student/exams", headers=auth(student)).json()[0]["latest_submission"]["attempt_number"] == 1


def test_draft_exams_cannot_be_reached_or_submitted(client: TestClient, teacher, student):
    exam = build_ready_exam(client, teacher)
    assert submit(client, student, exam["id"], script()).status_code == 404
    assert client.get(f"/api/student/exams/{uuid.uuid4().hex[:12]}", headers=auth(student)).status_code == 404


def test_only_students_can_submit(client: TestClient, teacher):
    exam = published_exam(client, teacher)
    assert submit(client, teacher, exam["id"], script()).status_code == 403


# --- Privacy ---------------------------------------------------------------

def test_submissions_are_private(client: TestClient, teacher, student, admin, make_client):
    exam = published_exam(client, teacher)
    submission = submit(client, student, exam["id"], script()).json()
    url = f"/api/submissions/{submission['id']}"
    file_url = f"{url}/files/{submission['files'][0]['id']}"

    other_student = register(make_client(), "student")
    other_teacher = register(make_client(), "teacher")
    for outsider in (other_student, other_teacher):
        assert client.get(url, headers=auth(outsider)).status_code == 404
        assert client.get(file_url, headers=auth(outsider)).status_code == 404
        assert client.get("/api/submissions", headers=auth(outsider)).json()["total"] == 0
    assert client.get("/api/submissions", headers=auth(admin)).status_code == 403
    assert client.get(url).status_code == 401


def test_teacher_can_search_by_student_id(client: TestClient, teacher, make_client):
    exam = published_exam(client, teacher)
    alice = register(make_client(), "student", full_name="Alice Rahman", student_id="2021-1111")
    bob = register(make_client(), "student", full_name="Bob Karim", student_id="2021-2222")
    for s in (alice, bob):
        submit(client, s, exam["id"], script(s["user"]["full_name"]))

    by_id = client.get("/api/submissions", headers=auth(teacher), params={"q": "2222"}).json()
    assert [s["student"]["full_name"] for s in by_id["items"]] == ["Bob Karim"]
    by_status = client.get("/api/submissions", headers=auth(teacher), params={"status": "uploaded"}).json()
    assert by_status["total"] == 2


# --- Exam lifecycle --------------------------------------------------------

def test_exam_cannot_be_unpublished_after_submissions(client: TestClient, teacher, student):
    exam = published_exam(client, teacher)
    submit(client, student, exam["id"], script())
    response = client.post(f"/api/exams/{exam['id']}/unpublish", headers=auth(teacher))
    assert response.status_code == 409 and "already submitted" in response.json()["detail"]


def test_dashboards_count_submissions(client: TestClient, teacher, student):
    course = client.post("/api/courses", headers=auth(teacher), json={"code": "CSE445", "name": "ML"}).json()
    section = client.post(f"/api/courses/{course['id']}/sections", headers=auth(teacher), json={"name": "1"}).json()
    client.post("/api/student/enrollments", headers=auth(student), json={"join_code": section["join_code"]})
    exam = published_exam(client, teacher, course_id=course["id"])

    before = client.get("/api/dashboard/student", headers=auth(student)).json()
    assert before["available_exam_count"] == 1 and before["submitted_exam_count"] == 0
    assert [e["title"] for e in before["upcoming_exams"]] == ["CSE445 Midterm"]

    submit(client, student, exam["id"], script())
    after = client.get("/api/dashboard/student", headers=auth(student)).json()
    assert after["submitted_exam_count"] == 1 and after["upcoming_exams"] == []
    assert after["recent_activity"][0]["summary"].startswith("Submitted attempt 1 for CSE445 Midterm")
    assert client.get("/api/dashboard/teacher", headers=auth(teacher)).json()["submission_count"] == 1
