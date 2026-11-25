from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, auth, register


def test_overview_counts_users_by_role(client: TestClient, admin, teacher, student):
    overview = client.get("/api/admin/overview", headers=auth(admin)).json()
    assert overview["total_users"] == 3
    assert overview["users_by_role"] == {"admin": 1, "teacher": 1, "student": 1}
    assert overview["new_users_last_7_days"] == 3


def test_user_listing_filters_and_paginates(client: TestClient, admin, make_client):
    for i in range(3):
        register(make_client(), "student", full_name=f"Student {i}")
    register(make_client(), "teacher", full_name="Only Teacher")
    headers = auth(admin)

    students = client.get("/api/admin/users", headers=headers, params={"role": "student", "page_size": 2}).json()
    assert students["total"] == 3 and len(students["items"]) == 2

    search = client.get("/api/admin/users", headers=headers, params={"q": "only"}).json()
    assert [u["full_name"] for u in search["items"]] == ["Only Teacher"]


def test_admin_user_update_rules(client: TestClient, admin, teacher, student):
    headers = auth(admin)
    me = admin["user"]["id"]
    assert client.patch(f"/api/admin/users/{me}", headers=headers, json={"is_active": False}).status_code == 400

    # A teacher without a student ID cannot be turned into a student.
    response = client.patch(f"/api/admin/users/{teacher['user']['id']}", headers=headers, json={"role": "student"})
    assert response.status_code == 400

    client.post("/api/courses", headers=auth(teacher), json={"code": "CSE1", "name": "Course"})
    response = client.patch(f"/api/admin/users/{teacher['user']['id']}", headers=headers, json={"role": "admin"})
    assert response.status_code == 409

    promoted = client.patch(f"/api/admin/users/{student['user']['id']}", headers=headers, json={"role": "teacher"})
    assert promoted.status_code == 200 and promoted.json()["role"] == "teacher"
    # Role change ends existing sessions.
    assert client.get("/api/auth/me", headers=auth(student)).status_code == 401


def test_deactivated_user_cannot_sign_in(client: TestClient, admin, make_client):
    session = register(make_client(), "teacher", email="gone@example.edu")
    client.patch(f"/api/admin/users/{session['user']['id']}", headers=auth(admin), json={"is_active": False})
    response = client.post("/api/auth/login", json={"email": "gone@example.edu", "password": PASSWORD})
    assert response.status_code == 403


def test_audit_log_records_actions_without_secrets(client: TestClient, admin, teacher):
    logs = client.get("/api/admin/audit-logs", headers=auth(admin), params={"action": "auth"}).json()
    actions = {item["action"] for item in logs["items"]}
    assert {"auth.register", "auth.login"} <= actions
    assert PASSWORD not in str(logs)


def test_system_status_reports_health(client: TestClient, admin):
    status = client.get("/api/admin/system", headers=auth(admin)).json()
    assert status["database_ok"] is True
    assert status["database_backend"] == "sqlite"
    assert status["migration_revision"]
    assert status["storage_writable"] is True
    assert status["active_sessions"] >= 1
