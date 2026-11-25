from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import PASSWORD, auth, register

COOKIE = get_settings().refresh_cookie_name


def test_register_teacher_sets_httponly_refresh_cookie(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"email": "Ada@Example.edu ", "password": PASSWORD, "full_name": "Ada", "role": "teacher"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "ada@example.edu"
    assert body["user"]["role"] == "teacher"
    assert body["user"]["student_id"] is None
    assert "refresh_token" not in body and "password_hash" not in body["user"]

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=")
    assert "HttpOnly" in cookie and "Path=/api/auth" in cookie and "SameSite=strict" in cookie


def test_student_registration_requires_student_id(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"email": "s@example.edu", "password": PASSWORD, "full_name": "Sam", "role": "student"},
    )
    assert response.status_code == 422
    assert "Student ID is required" in response.json()["detail"]


def test_admin_role_cannot_be_self_registered(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"email": "x@example.edu", "password": PASSWORD, "full_name": "Eve", "role": "admin"},
    )
    assert response.status_code == 422


def test_duplicate_email_and_student_id_are_rejected(client: TestClient):
    register(client, "student", email="dup@example.edu", student_id="2021-001")
    again = client.post(
        "/api/auth/register",
        json={"email": "DUP@example.edu", "password": PASSWORD, "full_name": "Dup", "role": "teacher"},
    )
    assert again.status_code == 409
    same_id = client.post(
        "/api/auth/register",
        json={"email": "other@example.edu", "password": PASSWORD, "full_name": "Other",
              "role": "student", "student_id": "2021-001"},
    )
    assert same_id.status_code == 409


def test_weak_password_reports_field_error(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"email": "w@example.edu", "password": "short", "full_name": "Weak", "role": "teacher"},
    )
    assert response.status_code == 422
    assert response.json()["fields"][0]["field"] == "password"


def test_login_success_and_generic_failure_message(client: TestClient):
    register(client, "teacher", email="t@example.edu")
    ok = client.post("/api/auth/login", json={"email": "t@example.edu", "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["user"]["last_login_at"] is not None

    wrong = client.post("/api/auth/login", json={"email": "t@example.edu", "password": "Wrong1234"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.edu", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_me_requires_valid_token(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    session = register(client)
    assert client.get("/api/auth/me", headers=auth(session)).json()["id"] == session["user"]["id"]


def test_refresh_rotates_and_detects_reuse(client: TestClient):
    register(client)
    first_cookie = client.cookies.get(COOKIE)

    rotated = client.post("/api/auth/refresh")
    assert rotated.status_code == 200
    second_cookie = client.cookies.get(COOKIE)
    assert second_cookie and second_cookie != first_cookie

    # Replaying the old token revokes the whole family, including the new token.
    client.cookies.set(COOKIE, first_cookie, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401
    client.cookies.set(COOKIE, second_cookie, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_refresh_token(client: TestClient):
    register(client)
    token = client.cookies.get(COOKIE)
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set(COOKIE, token, path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401


def test_password_change_signs_out_other_sessions(make_client):
    laptop, phone = make_client(), make_client()
    register(laptop, email="pw@example.edu")
    phone_session = phone.post("/api/auth/login", json={"email": "pw@example.edu", "password": PASSWORD}).json()
    laptop_session = laptop.post("/api/auth/login", json={"email": "pw@example.edu", "password": PASSWORD}).json()

    wrong = laptop.post("/api/users/me/password", headers=auth(laptop_session),
                        json={"current_password": "Nope12345", "new_password": "NewPassw0rd"})
    assert wrong.status_code == 400

    changed = laptop.post("/api/users/me/password", headers=auth(laptop_session),
                          json={"current_password": PASSWORD, "new_password": "NewPassw0rd"})
    assert changed.status_code == 200

    # Old access tokens stop working immediately; the phone's refresh token is revoked.
    assert laptop.get("/api/auth/me", headers=auth(laptop_session)).status_code == 401
    assert laptop.get("/api/auth/me", headers=auth(changed.json())).status_code == 200
    assert phone.get("/api/auth/me", headers=auth(phone_session)).status_code == 401
    assert phone.post("/api/auth/refresh").status_code == 401
    assert laptop.post("/api/auth/login", json={"email": "pw@example.edu", "password": "NewPassw0rd"}).status_code == 200


def test_profile_update(client: TestClient):
    session = register(client)
    response = client.patch("/api/users/me", headers=auth(session),
                            json={"full_name": "  Grace Hopper ", "institution": "NSU", "department": ""})
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Grace Hopper" and body["institution"] == "NSU" and body["department"] is None
    assert client.patch("/api/users/me", headers=auth(session), json={"full_name": None}).status_code == 422


def test_login_is_rate_limited(client: TestClient):
    for _ in range(10):
        client.post("/api/auth/login", json={"email": "x@example.edu", "password": "Wrong1234"})
    blocked = client.post("/api/auth/login", json={"email": "x@example.edu", "password": "Wrong1234"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
