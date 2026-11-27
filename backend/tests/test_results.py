"""Phase 6: result release modes, publication, student results, exports and analytics."""

import csv
import io


from tests.conftest import auth, register
from tests.test_ai_pipeline import ai, digital_script, score, set_up_ai  # noqa: F401
from tests.test_submissions import published_exam, submit
from tests.test_verification import Examiners, by_label

GRADES = {
    "1": [{"criteria": [{"id": "C1", "awarded": 4, "evidence": ["learn patterns from data"], "explanation": "Clear definition.",
                         "missing_concepts": ["a concrete example"]}], "feedback": "Add an example.", "missing_concepts": ["a concrete example"]}],
    "2(a)": [score(2, ["uses labelled examples"])],
}


def mark(client, teacher, student, ai, exam, grades=None) -> tuple[dict, dict]:
    ai.replies = [Examiners(grades or GRADES, {})] * 40
    submission = submit(client, student, exam["id"], digital_script()).json()
    evaluation = client.get(f"/api/submissions/{submission['id']}/evaluation", headers=auth(teacher)).json()
    return submission, evaluation


def approve(client, teacher, evaluation, comment: str | None = None) -> dict:
    if comment:
        client.put(f"/api/evaluations/{evaluation['id']}/review", headers=auth(teacher), json={
            "teacher_comment": comment,
            "questions": [{"question_id": by_label(evaluation)["1"]["question_id"], "teacher_comment": "See margin note."}],
        })
    response = client.post(f"/api/evaluations/{evaluation['id']}/approve", headers=auth(teacher))
    assert response.status_code == 200, response.text
    return response.json()


def setup(client, teacher, **exam_overrides) -> dict:
    exam = published_exam(client, teacher, **exam_overrides)
    set_up_ai(client, teacher, slots=("evaluator",))
    return exam


# --- Release after approval (default) --------------------------------------

def test_results_are_hidden_until_published(client, teacher, student, ai):
    exam = setup(client, teacher)
    submission, evaluation = mark(client, teacher, student, ai, exam)
    url = f"/api/results/{submission['id']}"

    assert client.get(url, headers=auth(student)).status_code == 404
    assert client.get("/api/student/results", headers=auth(student)).json() == []
    teacher_view = client.get(url, headers=auth(teacher)).json()
    assert teacher_view["provisional"] is True and teacher_view["total"] == 6.0

    early = client.post(f"/api/results/{submission['id']}/publish", headers=auth(teacher))
    assert early.status_code == 409 and "approved" in early.json()["detail"]

    approve(client, teacher, evaluation, comment="Well organised.")
    published = client.post(f"/api/results/{submission['id']}/publish", headers=auth(teacher)).json()
    assert published["provisional"] is False and published["published_at"]

    result = client.get(url, headers=auth(student))
    assert result.status_code == 200
    body = result.json()
    assert (body["total"], body["max_marks"], body["percentage"]) == (6.0, 15.0, 40.0)
    q1 = {q["label"]: q for q in body["questions"]}["1"]
    assert q1["awarded"] == 4.0 and q1["criteria"][0]["explanation"] == "Clear definition."
    assert q1["missing_concepts"] == ["a concrete example"] and q1["teacher_comment"] == "See margin note."
    assert body["teacher_comment"] == "Well organised."
    # Nothing about the AI or the review process reaches the student.
    for secret in ("gpt-test", "openai", "flags", "evidence", "verification", "model_answer"):
        assert secret not in result.text
    status = client.get(f"/api/submissions/{submission['id']}", headers=auth(student)).json()["status"]
    assert status == "published"


def test_teacher_comments_can_be_withheld(client, teacher, student, ai):
    exam = setup(client, teacher)
    client.patch(f"/api/exams/{exam['id']}/release-settings", headers=auth(teacher),
                 json={"result_release_mode": "after_approval", "release_teacher_comments": False})
    submission, evaluation = mark(client, teacher, student, ai, exam)
    approve(client, teacher, evaluation, comment="Private note for myself.")
    client.post(f"/api/results/{submission['id']}/publish", headers=auth(teacher))
    body = client.get(f"/api/results/{submission['id']}", headers=auth(student)).json()
    assert body["teacher_comment"] is None and all(q["teacher_comment"] is None for q in body["questions"])


def test_withdrawing_a_result_hides_it_again(client, teacher, student, ai):
    exam = setup(client, teacher)
    submission, evaluation = mark(client, teacher, student, ai, exam)
    approve(client, teacher, evaluation)
    client.post(f"/api/results/{submission['id']}/publish", headers=auth(teacher))
    assert client.post(f"/api/results/{submission['id']}/withdraw", headers=auth(teacher)).status_code == 204
    assert client.get(f"/api/results/{submission['id']}", headers=auth(student)).status_code == 404
    assert client.get(f"/api/submissions/{submission['id']}", headers=auth(teacher)).json()["status"] == "approved"
    # Published results cannot be reopened for review; withdrawn ones can.
    assert client.post(f"/api/evaluations/{evaluation['id']}/reopen", headers=auth(teacher)).status_code == 200


# --- Provisional release (mode A) ------------------------------------------

def test_provisional_results_are_visible_right_after_marking(client, teacher, student, ai):
    exam = setup(client, teacher)
    client.patch(f"/api/exams/{exam['id']}/release-settings", headers=auth(teacher),
                 json={"result_release_mode": "provisional", "release_teacher_comments": True})
    submission, evaluation = mark(client, teacher, student, ai, exam)
    client.put(f"/api/evaluations/{evaluation['id']}/review", headers=auth(teacher), json={"teacher_comment": "Draft thoughts."})

    body = client.get(f"/api/results/{submission['id']}", headers=auth(student)).json()
    assert body["provisional"] is True and body["total"] == 6.0
    assert body["teacher_comment"] is None  # review notes stay private until publication
    listing = client.get("/api/student/results", headers=auth(student)).json()
    assert listing[0]["provisional"] is True


# --- Bulk publication, roles -----------------------------------------------

def test_publish_all_approved_results(client, teacher, student, ai, make_client):
    exam = setup(client, teacher)
    s1, e1 = mark(client, teacher, student, ai, exam)
    approve(client, teacher, e1)
    other = register(make_client(), "student")
    mark(client, teacher, other, ai, exam)  # still under review

    result = client.post(f"/api/exams/{exam['id']}/publish-results", headers=auth(teacher)).json()
    assert result == {"published": 1, "skipped": 1}
    overview = client.get(f"/api/exams/{exam['id']}/results", headers=auth(teacher)).json()
    assert [r["published"] for r in overview["rows"]].count(True) == 1 and overview["approved_unpublished"] == 0


def test_results_are_private(client, teacher, student, ai, make_client):
    exam = setup(client, teacher)
    submission, evaluation = mark(client, teacher, student, ai, exam)
    approve(client, teacher, evaluation)
    client.post(f"/api/results/{submission['id']}/publish", headers=auth(teacher))

    other_student = register(make_client(), "student")
    other_teacher = register(make_client(), "teacher")
    for outsider in (other_student, other_teacher):
        assert client.get(f"/api/results/{submission['id']}", headers=auth(outsider)).status_code == 404
        assert client.get(f"/api/results/{submission['id']}/pdf", headers=auth(outsider)).status_code == 404
    assert client.get(f"/api/exams/{exam['id']}/analytics", headers=auth(other_teacher)).status_code == 404
    assert client.post(f"/api/results/{submission['id']}/publish", headers=auth(student)).status_code == 403
    assert client.get(f"/api/exams/{exam['id']}/results.csv", headers=auth(student)).status_code == 403


# --- Exports ---------------------------------------------------------------

def test_pdf_result_report(client, teacher, student, ai):
    import pymupdf

    exam = setup(client, teacher)
    submission, evaluation = mark(client, teacher, student, ai, exam)
    approve(client, teacher, evaluation)
    client.post(f"/api/results/{submission['id']}/publish", headers=auth(teacher))

    response = client.get(f"/api/results/{submission['id']}/pdf", headers=auth(student))
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    text = pymupdf.open(stream=response.content, filetype="pdf")[0].get_text()
    assert "CSE445 Midterm" in text and "6 / 15" in text and "Add an example." in text


def test_csv_export_neutralises_formulas(client, teacher, ai, make_client):
    exam = setup(client, teacher)
    attacker = register(make_client(), "student", full_name='=HYPERLINK("http://evil.example","Click")')
    submission, evaluation = mark(client, teacher, attacker, ai, exam)
    approve(client, teacher, evaluation)
    client.post(f"/api/results/{submission['id']}/publish", headers=auth(teacher))

    response = client.get(f"/api/exams/{exam['id']}/results.csv", headers=auth(teacher))
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0][:5] == ["Student ID", "Name", "Submission", "Status", "Final marks"]
    assert rows[0][-3:] == ["Q1", "Q2(a)", "Q2(b)"]
    assert rows[1][1].startswith("'=HYPERLINK")
    assert rows[1][4] == "6.00" and rows[1][7] == "yes" and rows[1][-3:] == ["4.0", "2.0", "0.0"]


# --- Analytics -------------------------------------------------------------

def test_analytics_use_approved_marks_only(client, teacher, ai, make_client):
    exam = setup(client, teacher)
    strong = {"1": [score(5, ["learn patterns from data"])], "2(a)": [score(4, ["uses labelled examples"])]}
    for grades in (GRADES, strong):
        s = register(make_client(), "student")
        _, evaluation = mark(client, teacher, s, ai, exam, grades)
        approve(client, teacher, evaluation)
    pending = register(make_client(), "student")
    mark(client, teacher, pending, ai, exam, {"1": [score(0, [])]})  # not approved: excluded

    stats = client.get(f"/api/exams/{exam['id']}/analytics", headers=auth(teacher)).json()
    assert (stats["total_submissions"], stats["graded_count"], stats["pending_evaluations"]) == (3, 2, 1)
    assert (stats["average"], stats["highest"], stats["lowest"], stats["median"]) == (7.5, 9.0, 6.0, 7.5)
    assert stats["average_percentage"] == 50.0
    assert {b["label"]: b["count"] for b in stats["distribution"]}["40–50%"] == 1
    assert {b["label"]: b["count"] for b in stats["distribution"]}["60–70%"] == 1
    questions = {q["label"]: q for q in stats["questions"]}
    assert questions["1"]["average"] == 4.5 and questions["1"]["average_percentage"] == 90.0
    assert questions["2(b)"]["average"] == 0.0 and questions["2(b)"]["answered"] == 0
    assert stats["weakest_questions"][0]["label"] == "2(b)"
    assert stats["common_missing_concepts"][0] == {"concept": "a concrete example", "count": 2}

    report = client.get(f"/api/exams/{exam['id']}/report.pdf", headers=auth(teacher))
    assert report.status_code == 200 and report.content.startswith(b"%PDF")


def test_analytics_with_no_approved_results(client, teacher, ai):
    exam = setup(client, teacher)
    stats = client.get(f"/api/exams/{exam['id']}/analytics", headers=auth(teacher)).json()
    assert stats["graded_count"] == 0 and stats["average"] is None and stats["common_missing_concepts"] == []
    assert sum(b["count"] for b in stats["distribution"]) == 0
