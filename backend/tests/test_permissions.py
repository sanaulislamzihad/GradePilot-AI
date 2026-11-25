import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth, register

TEACHER_ONLY = [
    ("get", "/api/courses"),
    ("post", "/api/courses"),
    ("get", "/api/dashboard/teacher"),
]
STUDENT_ONLY = [
    ("get", "/api/student/enrollments"),
    ("post", "/api/student/enrollments"),
    ("get", "/api/dashboard/student"),
]
ADMIN_ONLY = [
    ("get", "/api/admin/overview"),
    ("get", "/api/admin/users"),
    ("get", "/api/admin/audit-logs"),
    ("get", "/api/admin/system"),
]


def _call(client: TestClient, method: str, path: str, headers: dict | None = None):
    return getattr(client, method)(path, headers=headers or {}, **({"json": {}} if method == "post" else {}))


@pytest.mark.parametrize(("method", "path"), TEACHER_ONLY + STUDENT_ONLY + ADMIN_ONLY)
def test_protected_routes_require_authentication(client: TestClient, method: str, path: str):
    assert _call(client, method, path).status_code == 401


@pytest.mark.parametrize(("method", "path"), STUDENT_ONLY + ADMIN_ONLY)
def test_teacher_is_forbidden_from_other_roles(client: TestClient, teacher, method: str, path: str):
    assert _call(client, method, path, auth(teacher)).status_code == 403


@pytest.mark.parametrize(("method", "path"), TEACHER_ONLY + ADMIN_ONLY)
def test_student_is_forbidden_from_other_roles(client: TestClient, student, method: str, path: str):
    assert _call(client, method, path, auth(student)).status_code == 403


@pytest.mark.parametrize(("method", "path"), TEACHER_ONLY + STUDENT_ONLY)
def test_admin_does_not_inherit_teacher_or_student_dashboards(client: TestClient, admin, method: str, path: str):
    assert _call(client, method, path, auth(admin)).status_code == 403


def test_teacher_cannot_reach_another_teachers_course(client: TestClient, teacher, make_client):
    other = register(make_client(), "teacher")
    course = client.post("/api/courses", headers=auth(other), json={"code": "CSE101", "name": "Intro"}).json()
    section = client.post(f"/api/courses/{course['id']}/sections", headers=auth(other), json={"name": "1"}).json()

    headers = auth(teacher)
    assert client.get(f"/api/courses/{course['id']}", headers=headers).status_code == 404
    assert client.put(f"/api/courses/{course['id']}", headers=headers,
                      json={"code": "HACK", "name": "Hacked"}).status_code == 404
    assert client.delete(f"/api/courses/{course['id']}", headers=headers).status_code == 404
    assert client.get(f"/api/sections/{section['id']}/students", headers=headers).status_code == 404
    assert client.post(f"/api/sections/{section['id']}/join-code", headers=headers).status_code == 404
    assert client.get("/api/courses", headers=headers).json()["total"] == 0


def test_student_cannot_leave_someone_elses_enrollment(client: TestClient, teacher, student, make_client):
    course = client.post("/api/courses", headers=auth(teacher), json={"code": "CSE201", "name": "DS"}).json()
    section = client.post(f"/api/courses/{course['id']}/sections", headers=auth(teacher), json={"name": "1"}).json()
    other = register(make_client(), "student")
    enrollment = client.post("/api/student/enrollments", headers=auth(other),
                             json={"join_code": section["join_code"]}).json()

    response = client.delete(f"/api/student/enrollments/{enrollment['enrollment_id']}", headers=auth(student))
    assert response.status_code == 404


def test_deactivated_user_loses_access_immediately(client: TestClient, admin, teacher):
    headers = auth(teacher)
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    client.patch(f"/api/admin/users/{teacher['user']['id']}", headers=auth(admin), json={"is_active": False})
    assert client.get("/api/auth/me", headers=headers).status_code == 401
