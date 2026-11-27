"""List endpoints must not run extra queries per row (N+1).

Each endpoint is called with one marked submission and again with four; the number
of SQL statements has to stay the same.
"""

from contextlib import contextmanager

import pytest
from sqlalchemy import event

from app.database.session import engine
from tests.conftest import auth, register
from tests.test_ai_pipeline import ai, digital_script, score, set_up_ai  # noqa: F401
from tests.test_submissions import published_exam, submit
from tests.test_verification import Examiners

GRADES = {"1": [score(4, ["learn patterns from data"])], "2(a)": [score(2, ["uses labelled examples"])]}


@contextmanager
def count_queries():
    statements: list[str] = []

    def _record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _record)


def add_marked_submission(client, teacher, ai, exam, make_client, approve: bool = True) -> dict:
    student = register(make_client(), "student")
    ai.replies = [Examiners(GRADES, {})] * 40
    submission = submit(client, student, exam["id"], digital_script()).json()
    evaluation = client.get(f"/api/submissions/{submission['id']}/evaluation", headers=auth(teacher)).json()
    if approve:
        client.post(f"/api/evaluations/{evaluation['id']}/approve", headers=auth(teacher))
        client.post(f"/api/results/{submission['id']}/publish", headers=auth(teacher))
    return student


def queries(client, headers, url) -> int:
    with count_queries() as statements:
        response = client.get(url, headers=headers)
    assert response.status_code == 200, response.text
    return len(statements)


@pytest.mark.parametrize(
    "url",
    [
        "/api/exams",
        "/api/submissions?exam_id={exam}",
        "/api/evaluations?exam_id={exam}",
        "/api/exams/{exam}/results",
        "/api/exams/{exam}/analytics",
        "/api/exams/{exam}/results.csv",
        "/api/dashboard/teacher",
    ],
)
def test_teacher_lists_use_a_fixed_number_of_queries(client, teacher, ai, make_client, url):
    exam = published_exam(client, teacher)
    set_up_ai(client, teacher, slots=("evaluator",))
    target = url.format(exam=exam["id"])

    add_marked_submission(client, teacher, ai, exam, make_client)
    with_one = queries(client, auth(teacher), target)
    for _ in range(3):
        add_marked_submission(client, teacher, ai, exam, make_client)
    with_four = queries(client, auth(teacher), target)

    assert with_four == with_one, f"{target}: {with_one} queries for 1 row, {with_four} for 4"


@pytest.mark.parametrize("url", ["/api/student/results", "/api/submissions", "/api/dashboard/student", "/api/student/exams"])
def test_student_lists_use_a_fixed_number_of_queries(client, teacher, student, ai, url):
    set_up_ai(client, teacher, slots=("evaluator",))

    def submit_and_publish():
        exam = published_exam(client, teacher)
        ai.replies = [Examiners(GRADES, {})] * 40
        submission = submit(client, student, exam["id"], digital_script()).json()
        evaluation = client.get(f"/api/submissions/{submission['id']}/evaluation", headers=auth(teacher)).json()
        client.post(f"/api/evaluations/{evaluation['id']}/approve", headers=auth(teacher))
        client.post(f"/api/results/{submission['id']}/publish", headers=auth(teacher))

    submit_and_publish()
    with_one = queries(client, auth(student), url)
    for _ in range(3):
        submit_and_publish()
    with_four = queries(client, auth(student), url)
    assert with_four == with_one, f"{url}: {with_one} queries for 1 row, {with_four} for 4"
