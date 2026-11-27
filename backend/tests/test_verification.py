"""Phase 5: SymPy checks, similarity signal, independent verifier and teacher review."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.services import math_check, similarity
from tests.conftest import auth
from tests.test_ai_pipeline import QUESTION_KEYS, Grader, ai, digital_script, score, set_up_ai, user_text  # noqa: F401
from tests.test_exams import make_pdf
from tests.test_submissions import published_exam, submit


# --- SymPy -----------------------------------------------------------------

@pytest.mark.parametrize(
    ("model", "student", "status"),
    [
        ("2x + 3 = 11, so 2x = 8 and x = 4.", "2x + 3 = 11\n2x = 8\nx = 4. Check: 2(4) + 3 = 11", "match"),
        ("x = 1/2", "x = 0.5", "match"),             # equivalent forms
        ("Answer: 2*pi", "Answer = 2pi", "match"),
        ("x = 2, y = 3", "y = 3 and x = 2", "match"),
        ("x = 4", "2x + 3 = 11\n2x = 9\nx = 4.5", "mismatch"),
        ("x = 4", "the answer is four", "uncertain"),
        ("x = 2, y = 3", "y = 3", "uncertain"),
    ],
)
def test_math_check_outcomes(model, student, status):
    assert math_check.check(model, student).status == status


def test_math_check_locates_the_wrong_step():
    result = math_check.check("x = 4", "2x + 3 = 11\n2x = 9\nx = 4.5")
    assert [e["line"] for e in result.step_errors] == [2, 3]


@pytest.mark.parametrize("payload", ['__import__("os").system("x")', "exec(1)", "open(1)", "lambda: 1", "a.b", "x" * 200])
def test_math_parser_refuses_anything_but_plain_maths(payload):
    assert math_check.safe_parse(payload) is None


# --- Verification in the pipeline ------------------------------------------

def verdict(suggested: float, fair: bool = True, rubric: bool = True, evidence: bool = True) -> dict:
    return {
        "criteria": [{"id": "C1", "fair": fair, "suggested_awarded": suggested, "note": "Checked."}],
        "rubric_followed": rubric, "evidence_supports_marks": evidence,
        "missed_valid_concepts": [], "unsupported_assumptions": [], "comment": "Second opinion.",
    }


class Examiners:
    """Mock provider that plays both the evaluator and the verifier."""

    def __init__(self, grades: dict[str, list[dict]], verdicts: dict[str, list[dict]]) -> None:
        self.grader = Grader(grades)
        self.verdicts = verdicts
        self.verifier_prompts: dict[str, list[str]] = {}

    def __call__(self, body: dict):
        text = user_text(body)
        if "First examiner's marks" not in text:
            return self.grader(body)
        label = next(v for k, v in QUESTION_KEYS.items() if k in text)
        self.verifier_prompts.setdefault(label, []).append(text)
        queue = self.verdicts.get(label) or [verdict(0)]
        reply = queue.pop(0) if len(queue) > 1 else queue[0]
        return httpx.Response(200, json={"model": "gpt-test", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(reply)}}],
                                         "usage": {"prompt_tokens": 5, "completion_tokens": 5}})


def run(client, teacher, student, ai, examiners: Examiners, slots=("evaluator", "verifier"), exam=None, files=None) -> tuple[dict, dict]:
    exam = exam or published_exam(client, teacher)
    set_up_ai(client, teacher, slots=slots)
    ai.replies = [examiners] * 60
    submission = submit(client, student, exam["id"], files or digital_script()).json()
    evaluation = client.get(f"/api/submissions/{submission['id']}/evaluation", headers=auth(teacher)).json()
    return submission, evaluation


def by_label(evaluation: dict) -> dict[str, dict]:
    return {q["label"]: q for q in evaluation["questions"]}


def test_verifier_agreement_and_disagreement(client, teacher, student, ai):
    examiners = Examiners(
        {"1": [score(5, ["learn patterns from data"])], "2(a)": [score(3, ["uses labelled examples"])]},
        {"1": [verdict(4.5)], "2(a)": [verdict(1, fair=False)]},  # 2(a): 2 marks apart on a 4-mark question
    )
    submission, evaluation = run(client, teacher, student, ai, examiners)
    assert submission["status"] == "teacher_review_required"
    assert evaluation["verification_status"] == "completed"

    q1, q2a = by_label(evaluation)["1"], by_label(evaluation)["2(a)"]
    assert q1["verification"]["verdict"] == "agrees" and "verifier_disagrees" not in q1["flags"]
    assert q2a["verification"]["verdict"] == "disagrees" and q2a["verification"]["suggested_awarded"] == 1.0
    assert "verifier_disagrees" in q2a["flags"] and "verifier_disagrees" in evaluation["flags"]
    # Disagreement is flagged, never averaged: the evaluator's marks stand until the teacher decides.
    assert q2a["awarded"] == 3.0 and q2a["final_awarded"] == 3.0
    # The verifier saw the first examiner's marks and evidence.
    assert 'First examiner awarded 3. Evidence: "uses labelled examples"' in examiners.verifier_prompts["2(a)"][0]
    assert q1["verification"]["same_model_as_evaluator"] is True


def test_verifier_doubts_about_rubric_or_evidence_are_flagged(client, teacher, student, ai):
    examiners = Examiners({"1": [score(5, ["learn patterns from data"])]}, {"1": [verdict(5, evidence=False)]})
    _, evaluation = run(client, teacher, student, ai, examiners)
    assert "verifier_disagrees" in by_label(evaluation)["1"]["flags"]


def test_broken_verifier_output_does_not_block_review(client, teacher, student, ai):
    bad = {"criteria": [{"id": "C9", "fair": True, "suggested_awarded": 99, "note": "?"}], "rubric_followed": True,
           "evidence_supports_marks": True, "missed_valid_concepts": [], "unsupported_assumptions": [], "comment": ""}
    examiners = Examiners({}, {"1": [bad], "2(a)": [bad]})
    submission, evaluation = run(client, teacher, student, ai, examiners)
    assert submission["status"] == "teacher_review_required"
    assert evaluation["verification_status"] == "failed"
    assert "verification_failed" in by_label(evaluation)["1"]["flags"]


def test_without_a_verifier_local_checks_still_run(client, teacher, student, ai, monkeypatch):
    monkeypatch.setattr(similarity, "score", lambda answer, reference: 0.1)  # unrelated to the model answer
    examiners = Examiners({"1": [score(5, ["learn patterns from data"])]}, {})
    _, evaluation = run(client, teacher, student, ai, examiners, slots=("evaluator",))
    assert evaluation["verification_status"] == "skipped"
    q1 = by_label(evaluation)["1"]
    assert q1["similarity"] == 0.1 and "similarity_mismatch" in q1["flags"] and q1["verification"] is None


def test_sympy_checks_mathematical_answers(client, teacher, student, ai):
    from tests.test_exams import create_exam

    exam = create_exam(client, teacher, total_marks=5)
    exam = client.post(f"/api/exams/{exam['id']}/questions", headers=auth(teacher),
                       json={"text": "Solve 2x + 3 = 11.", "marks": 5, "question_type": "mathematical"}).json()
    qid = exam["questions"][0]["id"]
    client.put(f"/api/questions/{qid}/model-answer", headers=auth(teacher), json={"content": "2x = 8, so x = 4", "approved": True})
    client.put(f"/api/questions/{qid}/rubric", headers=auth(teacher),
               json={"approved": True, "criteria": [{"name": "Working", "max_marks": 3}, {"name": "Answer", "max_marks": 2}]})
    exam = client.post(f"/api/exams/{exam['id']}/publish", headers=auth(teacher)).json()

    QUESTION_KEYS["Solve 2x"] = "m"
    try:
        full_marks = {"criteria": [
            {"id": "C1", "awarded": 3, "evidence": ["2x = 9"], "explanation": "ok", "missing_concepts": []},
            {"id": "C2", "awarded": 2, "evidence": ["x = 4.5"], "explanation": "ok", "missing_concepts": []}],
            "feedback": "Correct.", "missing_concepts": []}
        examiners = Examiners({"m": [full_marks]}, {})
        script = [("maths.pdf", make_pdf(["1. 2x + 3 = 11", "2x = 9", "x = 4.5"]))]
        _, evaluation = run(client, teacher, student, ai, examiners, slots=("evaluator",), exam=exam, files=script)
    finally:
        QUESTION_KEYS.pop("Solve 2x")
    question = evaluation["questions"][0]
    assert question["math_check"]["status"] == "mismatch"
    assert [e["text"] for e in question["math_check"]["step_errors"]] == ["2x = 9", "x = 4.5"]
    assert "math_disagrees" in question["flags"]  # full marks for a wrong final answer


# --- Teacher review --------------------------------------------------------

def reviewed(client, teacher, student, ai, grades=None):
    examiners = Examiners(grades or {"1": [score(4, ["learn patterns from data"])], "2(a)": [score(2, ["uses labelled examples"])]}, {})
    return run(client, teacher, student, ai, examiners, slots=("evaluator",))


def test_teacher_overrides_are_validated_and_totals_recomputed(client, teacher, student, ai):
    submission, evaluation = reviewed(client, teacher, student, ai)
    assert (evaluation["total_awarded"], evaluation["final_total"]) == (6.0, 6.0)
    q1 = by_label(evaluation)["1"]
    url = f"/api/evaluations/{evaluation['id']}/review"

    too_high = client.put(url, headers=auth(teacher), json={"questions": [
        {"question_id": q1["question_id"], "criteria": [{"criterion_id": q1["criteria"][0]["id"], "teacher_awarded": 6}]}]})
    assert too_high.status_code == 422 and "between 0 and 5" in too_high.json()["detail"]

    updated = client.put(url, headers=auth(teacher), json={
        "questions": [
            {"question_id": q1["question_id"], "criteria": [{"criterion_id": q1["criteria"][0]["id"], "teacher_awarded": 5}],
             "teacher_comment": "Example was given in the margin."},
            {"question_id": by_label(evaluation)["2(b)"]["question_id"], "teacher_awarded": 1.5},
        ],
        "teacher_comment": "Checked against the paper.",
    }).json()
    questions = by_label(updated)
    assert questions["1"]["awarded"] == 4.0 and questions["1"]["final_awarded"] == 5.0  # AI mark kept for the record
    assert questions["2(b)"]["final_awarded"] == 1.5
    assert updated["total_awarded"] == 6.0 and updated["final_total"] == 8.5
    assert updated["teacher_comment"] == "Checked against the paper."

    history = client.get(f"/api/evaluations/{evaluation['id']}/history", headers=auth(teacher)).json()
    changes = history[0]["changes"]
    assert {"question": "1", "field": "criterion 'Correctness'", "old": None, "new": "5"} in changes
    assert {"question": "2(b)", "field": "question mark", "old": None, "new": "1.5"} in changes


def test_approve_requires_marks_for_every_question(client, teacher, student, ai):
    over = score(99, [])
    submission, evaluation = reviewed(client, teacher, student, ai, grades={"1": [over, over, over]})
    q1 = by_label(evaluation)["1"]
    assert q1["awarded"] is None and evaluation["final_total"] is None

    refused = client.post(f"/api/evaluations/{evaluation['id']}/approve", headers=auth(teacher))
    assert refused.status_code == 422 and "question 1" in refused.json()["detail"]

    client.put(f"/api/evaluations/{evaluation['id']}/review", headers=auth(teacher),
               json={"questions": [{"question_id": q1["question_id"], "teacher_awarded": 3}]})
    approved = client.post(f"/api/evaluations/{evaluation['id']}/approve", headers=auth(teacher)).json()
    assert approved["review_status"] == "approved" and approved["final_total"] == 4.0 and approved["reviewed_by"] == "Ada Teacher"
    detail = client.get(f"/api/submissions/{submission['id']}", headers=auth(student)).json()
    assert detail["status"] == "approved"

    # Locked once approved, until reopened.
    locked = client.put(f"/api/evaluations/{evaluation['id']}/review", headers=auth(teacher), json={"teacher_comment": "x"})
    assert locked.status_code == 409
    reopened = client.post(f"/api/evaluations/{evaluation['id']}/reopen", headers=auth(teacher)).json()
    assert reopened["review_status"] == "pending"
    assert client.get(f"/api/submissions/{submission['id']}", headers=auth(teacher)).json()["status"] == "teacher_review_required"


def test_reject_runs_a_fresh_marking(client, teacher, student, ai):
    submission, evaluation = reviewed(client, teacher, student, ai)
    rejected = client.post(f"/api/evaluations/{evaluation['id']}/reject", headers=auth(teacher),
                           json={"reason": "Marks for 2(a) are too harsh."})
    assert rejected.status_code == 200 and rejected.json()["status"] == "teacher_review_required"

    current = client.get(f"/api/submissions/{submission['id']}/evaluation", headers=auth(teacher)).json()
    assert current["run_number"] == 2 and current["review_status"] == "pending"
    old = client.get(f"/api/evaluations/{evaluation['id']}", headers=auth(teacher)).json()
    assert old["is_current"] is False and old["review_status"] == "rejected" and old["teacher_comment"] == "Marks for 2(a) are too harsh."
    history = client.get(f"/api/evaluations/{current['id']}/history", headers=auth(teacher)).json()
    assert history[0]["action"] == "evaluation.reject"


def test_bulk_approval_skips_flagged_evaluations_and_queue_orders_them(client, teacher, student, ai, make_client):
    from tests.conftest import register

    exam = published_exam(client, teacher)
    set_up_ai(client, teacher, slots=("evaluator",))
    clean = Examiners({"1": [score(4, ["learn patterns from data"])], "2(a)": [score(2, ["uses labelled examples"])]}, {})
    ai.replies = [clean] * 30
    submit(client, student, exam["id"], digital_script())
    other = register(make_client(), "student")
    flagged = Examiners({"1": [score(5, ["not in the answer at all"])]}, {})
    ai.replies = [flagged] * 30
    submit(client, other, exam["id"], digital_script())

    queue = client.get("/api/evaluations", headers=auth(teacher), params={"exam_id": exam["id"]}).json()
    assert len(queue) == 2 and "evidence_not_found" in queue[0]["flags"]  # flagged first
    assert len(client.get("/api/evaluations", headers=auth(teacher), params={"flagged_only": True}).json()) == 1

    result = client.post(f"/api/exams/{exam['id']}/approve-unflagged", headers=auth(teacher)).json()
    assert result == {"approved": 1, "skipped": 1}
    statuses = {i["review_status"] for i in client.get("/api/evaluations", headers=auth(teacher)).json()}
    assert statuses == {"approved", "pending"}


def test_students_cannot_review(client, teacher, student, ai):
    submission, evaluation = reviewed(client, teacher, student, ai)
    for method, path in [("put", "review"), ("post", "approve"), ("post", "reject"), ("get", "history")]:
        response = getattr(client, method)(f"/api/evaluations/{evaluation['id']}/{path}", headers=auth(student),
                                           **({"json": {"reason": "please"}} if method != "get" else {}))
        assert response.status_code == 403
    assert client.get("/api/evaluations", headers=auth(student)).status_code == 403
