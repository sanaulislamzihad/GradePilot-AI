"""Phase 7: production configuration guard, shared rate limits, request limits and headers."""

import fakeredis
import pytest
import redis
from pydantic import ValidationError

from app.api import deps
from app.core.config import Settings
from app.security.rate_limit import MemoryLimiter, RedisLimiter
from tests.conftest import auth, register

SECRET = "x" * 40
SAFE_PRODUCTION = {
    "environment": "production",
    "jwt_secret_key": SECRET,
    "cookie_secure": True,
    "encryption_keys": "k1:" + "A" * 43 + "=",
    "database_url": "postgresql+psycopg://app:pw@db:5432/gradepilot",
    "celery_broker_url": "redis://redis:6379/0",
}


# --- Production configuration ------------------------------------------------

def test_safe_production_settings_are_accepted():
    assert Settings(_env_file=None, **SAFE_PRODUCTION).environment == "production"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"encryption_keys": ""}, "ENCRYPTION_KEYS"),
        ({"encryption_keys": "replace-with-generated-key"}, "ENCRYPTION_KEYS"),
        ({"database_url": "sqlite:///./gradepilot.db"}, "PostgreSQL"),
        ({"celery_broker_url": "sqla+sqlite:///broker.db"}, "Redis"),
    ],
)
def test_unsafe_production_settings_refuse_to_start(override, message):
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **{**SAFE_PRODUCTION, **override})


def test_development_settings_are_not_restricted():
    Settings(_env_file=None, environment="development", jwt_secret_key=SECRET, cookie_secure=False)


# --- Redis limiter -------------------------------------------------------------

def test_redis_limiter_shares_counts_between_workers():
    server = fakeredis.FakeServer()
    worker_a = RedisLimiter("auth", 3, 60, fakeredis.FakeRedis(server=server))
    worker_b = RedisLimiter("auth", 3, 60, fakeredis.FakeRedis(server=server))

    assert [worker_a.hit("ip"), worker_b.hit("ip"), worker_a.hit("ip")] == [None, None, None]
    wait = worker_b.hit("ip")
    assert wait is not None and 1 <= wait <= 61
    assert worker_a.hit("other-ip") is None  # keys are independent

    worker_a.reset("ip")
    assert worker_b.hit("ip") is None


def test_redis_limiter_allows_requests_when_redis_is_down(caplog):
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server)
    limiter = RedisLimiter("auth", 1, 60, client)
    server.connected = False  # every command now raises ConnectionError
    assert limiter.hit("ip") is None and limiter.hit("ip") is None
    assert "Rate limiter unavailable" in caplog.text
    with pytest.raises(redis.ConnectionError):
        client.ping()


def test_memory_limiter_window():
    limiter = MemoryLimiter("t", 2, 60)
    assert limiter.hit("k") is None and limiter.hit("k") is None
    assert limiter.hit("k") is not None


# --- Limits on uploads and AI work --------------------------------------------

def test_upload_rate_limit(client, student, monkeypatch):
    monkeypatch.setattr(deps.upload_limiter, "max_attempts", 2)
    url = "/api/exams/00000000-0000-0000-0000-000000000000/submissions"
    codes = [client.post(url, headers=auth(student)).status_code for _ in range(3)]
    assert codes[:2] != [429, 429] and codes[2] == 429


def test_ai_rate_limit_is_per_user(client, teacher, make_client, monkeypatch):
    monkeypatch.setattr(deps.ai_limiter, "max_attempts", 1)
    first = client.post("/api/providers/test", headers=auth(teacher), json={"provider": "openai"})
    second = client.post("/api/providers/test", headers=auth(teacher), json={"provider": "openai"})
    assert first.status_code != 429
    assert second.status_code == 429 and int(second.headers["Retry-After"]) > 0
    other = register(make_client(), "teacher")
    assert client.post("/api/providers/test", headers=auth(other), json={"provider": "openai"}).status_code != 429


# --- Request size and headers -------------------------------------------------

def test_oversized_requests_are_rejected_before_reading(client):
    response = client.post("/api/auth/login", content=b"{}", headers={
        "content-type": "application/json", "content-length": str(500 * 1024 * 1024),
    })
    assert response.status_code == 413 and "too large" in response.json()["detail"]


def test_security_headers(client):
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert "strict-transport-security" not in headers  # only in production
    # The interactive docs load their own scripts, so they are not given the API policy.
    assert "content-security-policy" not in client.get("/api/docs").headers
