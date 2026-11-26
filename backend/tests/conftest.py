"""Test fixtures.

Environment variables are set before the app is imported, so the engine and
settings point at a throwaway SQLite database created through Alembic.
"""

import os
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="gradepilot-tests-"))
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
        "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256-signing",
        "STORAGE_DIR": str(_TMP / "storage"),
        "AUTH_RATE_LIMIT_ATTEMPTS": "10",
        # Fixed test-only key (base64 of 32 bytes); never used outside the test suite.
        "ENCRYPTION_KEYS": "test:" + "A" * 43 + "=",
        "CELERY_TASK_ALWAYS_EAGER": "true",
        "ALLOW_CUSTOM_AI_ENDPOINTS": "false",
    }
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import auth_limiter  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.security.passwords import hash_password  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
PASSWORD = "Passw0rd!"
SEEDED_TABLES = {"ai_providers"}


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> Iterator[None]:
    command.upgrade(alembic_config(os.environ["DATABASE_URL"]), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            # Reference data seeded by migrations stays in place.
            if table.name not in SEEDED_TABLES:
                conn.execute(table.delete())
    auth_limiter.reset()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_client() -> Iterator[Callable[[], TestClient]]:
    """Separate clients have separate cookie jars, like separate browsers."""
    clients: list[TestClient] = []

    def _make() -> TestClient:
        new_client = TestClient(app)
        clients.append(new_client)
        return new_client

    yield _make
    for c in clients:
        c.close()


def register(client: TestClient, role: str = "teacher", email: str | None = None, **extra) -> dict:
    payload = {
        "email": email or f"{role}-{os.urandom(4).hex()}@example.edu",
        "password": PASSWORD,
        "full_name": extra.pop("full_name", f"Test {role.title()}"),
        "role": role,
        **extra,
    }
    if role == "student" and "student_id" not in payload:
        payload["student_id"] = f"S-{os.urandom(3).hex()}"
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def auth(token_response: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_response['access_token']}"}


@pytest.fixture
def teacher(make_client) -> dict:
    return register(make_client(), "teacher", full_name="Ada Teacher")


@pytest.fixture
def student(make_client) -> dict:
    return register(make_client(), "student", full_name="Sam Student")


@pytest.fixture
def admin(client: TestClient) -> dict:
    with SessionLocal() as db:
        user = User(
            email="admin@example.edu",
            full_name="Root Admin",
            password_hash=hash_password(PASSWORD),
            role=UserRole.ADMIN,
        )
        db.add(user)
        db.commit()
    response = client.post("/api/auth/login", json={"email": "admin@example.edu", "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()
