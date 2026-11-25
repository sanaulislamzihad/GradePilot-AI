from fastapi.testclient import TestClient

from tests.conftest import auth, register


def _course(client: TestClient, teacher: dict, code: str = "CSE445", name: str = "Machine Learning") -> dict:
    response = client.post("/api/courses", headers=auth(teacher), json={"code": code, "name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _section(client: TestClient, teacher: dict, course_id: str, name: str = "1") -> dict:
    response = client.post(f"/api/courses/{course_id}/sections", headers=auth(teacher), json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_course_crud_and_validation(client: TestClient, teacher):
    headers = auth(teacher)
    course = _course(client, teacher, code="cse 445")
    assert course["code"] == "CSE 445" and course["sections"] == []

    assert client.post("/api/courses", headers=headers, json={"code": "CSE 445", "name": "Again"}).status_code == 409
    assert client.post("/api/courses", headers=headers, json={"code": "", "name": "X"}).status_code == 422

    _course(client, teacher, code="CSE 115", name="Programming")
    listing = client.get("/api/courses", headers=headers, params={"q": "machine"}).json()
    assert listing["total"] == 1 and listing["items"][0]["name"] == "Machine Learning"

    updated = client.put(f"/api/courses/{course['id']}", headers=headers,
                         json={"code": "CSE 445", "name": "Applied ML", "description": "Fall term"})
    assert updated.status_code == 200 and updated.json()["description"] == "Fall term"

    assert client.delete(f"/api/courses/{course['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/courses/{course['id']}", headers=headers).status_code == 404


def test_sections_and_join_codes(client: TestClient, teacher):
    headers = auth(teacher)
    course = _course(client, teacher)
    section = _section(client, teacher, course["id"], "A")
    assert len(section["join_code"]) == 8 and section["is_open"] is True

    duplicate = client.post(f"/api/courses/{course['id']}/sections", headers=headers, json={"name": "a"})
    assert duplicate.status_code == 409

    regenerated = client.post(f"/api/sections/{section['id']}/join-code", headers=headers).json()
    assert regenerated["join_code"] != section["join_code"]

    closed = client.patch(f"/api/sections/{section['id']}", headers=headers, json={"is_open": False}).json()
    assert closed["is_open"] is False

    detail = client.get(f"/api/courses/{course['id']}", headers=headers).json()
    assert detail["section_count"] == 1 and detail["sections"][0]["name"] == "A"


def test_student_enrollment_flow(client: TestClient, teacher, student, make_client):
    course = _course(client, teacher)
    section_one = _section(client, teacher, course["id"], "1")
    section_two = _section(client, teacher, course["id"], "2")

    bad = client.post("/api/student/enrollments", headers=auth(student), json={"join_code": "ZZZZZZZZ"})
    assert bad.status_code == 404

    joined = client.post("/api/student/enrollments", headers=auth(student),
                         json={"join_code": section_one["join_code"].lower()})
    assert joined.status_code == 201
    enrollment = joined.json()
    assert enrollment["course_code"] == "CSE445" and enrollment["teacher_name"] == "Ada Teacher"

    again = client.post("/api/student/enrollments", headers=auth(student), json={"join_code": section_one["join_code"]})
    assert again.status_code == 409
    other_section = client.post("/api/student/enrollments", headers=auth(student),
                                json={"join_code": section_two["join_code"]})
    assert other_section.status_code == 409

    client.patch(f"/api/sections/{section_two['id']}", headers=auth(teacher), json={"is_open": False})
    late = register(make_client(), "student")
    closed = client.post("/api/student/enrollments", headers=auth(late), json={"join_code": section_two["join_code"]})
    assert closed.status_code == 409

    roster = client.get(f"/api/sections/{section_one['id']}/students", headers=auth(teacher)).json()
    assert [s["full_name"] for s in roster] == ["Sam Student"]

    removed = client.delete(f"/api/sections/{section_one['id']}/students/{roster[0]['enrollment_id']}",
                            headers=auth(teacher))
    assert removed.status_code == 204
    assert client.get("/api/student/enrollments", headers=auth(student)).json() == []


def test_student_can_leave_section(client: TestClient, teacher, student):
    course = _course(client, teacher)
    section = _section(client, teacher, course["id"])
    enrollment = client.post("/api/student/enrollments", headers=auth(student),
                             json={"join_code": section["join_code"]}).json()
    assert client.delete(f"/api/student/enrollments/{enrollment['enrollment_id']}",
                         headers=auth(student)).status_code == 204


def test_dashboards_reflect_database_state(client: TestClient, teacher, student, make_client):
    empty = client.get("/api/dashboard/teacher", headers=auth(teacher)).json()
    assert (empty["course_count"], empty["section_count"], empty["student_count"]) == (0, 0, 0)

    course_a = _course(client, teacher, "CSE101", "Intro")
    course_b = _course(client, teacher, "CSE102", "Next")
    section_a = _section(client, teacher, course_a["id"])
    section_b = _section(client, teacher, course_b["id"])
    second_student = register(make_client(), "student")
    for s in (student, second_student):
        client.post("/api/student/enrollments", headers=auth(s), json={"join_code": section_a["join_code"]})
    client.post("/api/student/enrollments", headers=auth(student), json={"join_code": section_b["join_code"]})

    dashboard = client.get("/api/dashboard/teacher", headers=auth(teacher)).json()
    assert dashboard["course_count"] == 2
    assert dashboard["section_count"] == 2
    assert dashboard["student_count"] == 2  # distinct students across courses
    assert dashboard["recent_activity"][0]["summary"].startswith("Added section")

    student_view = client.get("/api/dashboard/student", headers=auth(student)).json()
    assert student_view["enrollment_count"] == 2 and student_view["course_count"] == 2
