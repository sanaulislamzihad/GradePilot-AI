import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.ai import ModelConfig, UsageLog, UserApiKey
from app.providers import runtime
from app.providers.base import AIInvalidResponseError, AIRequest
from app.services import ai_router
from tests.ai_mocks import OpenAIStub, transport
from tests.conftest import auth, register

VALID_KEY = "sk-test-valid-key-1234"


@pytest.fixture
def stub(monkeypatch):
    """An OpenAI-compatible mock server shared by every adapter call in the test."""
    server = OpenAIStub(models=("gpt-test", "gpt-vision"))
    mock, recorder = transport(server)
    monkeypatch.setattr(runtime, "transport", mock)
    monkeypatch.setattr(ai_router, "sleep", lambda seconds: None)
    server.recorder = recorder
    return server


def connect(client: TestClient, teacher: dict, key: str = VALID_KEY, provider: str = "openai"):
    return client.post("/api/providers/connect", headers=auth(teacher), json={"provider": provider, "api_key": key})


def configure(client: TestClient, teacher: dict, slot: str = "evaluator", model: str = "gpt-test"):
    connect(client, teacher)
    response = client.put(f"/api/model-configs/{slot}", headers=auth(teacher), json={"provider": "openai", "model": model})
    assert response.status_code == 200, response.text
    return response.json()


# --- Provider keys ---------------------------------------------------------

def test_connect_stores_only_an_encrypted_key(client: TestClient, teacher, stub):
    response = connect(client, teacher)
    assert response.status_code == 200, response.text
    connection = response.json()["connection"]
    assert connection["key_hint"] == "…1234" and connection["status"] == "valid"
    assert VALID_KEY not in response.text

    with SessionLocal() as db:
        stored = db.scalar(select(UserApiKey))
        assert VALID_KEY not in stored.encrypted_key and stored.encrypted_key.startswith("test$")

    listing = client.get("/api/providers", headers=auth(teacher))
    assert VALID_KEY not in listing.text
    slugs = [p["slug"] for p in listing.json()]
    assert "openai" in slugs and "anthropic" in slugs and "custom" not in slugs


def test_rejected_key_is_not_saved(client: TestClient, teacher, stub):
    response = connect(client, teacher, key="sk-wrong-key-0000")
    assert response.status_code == 400 and "rejected" in response.json()["detail"]
    with SessionLocal() as db:
        assert db.scalar(select(UserApiKey)) is None


def test_key_saved_as_unverified_when_provider_unreachable(client: TestClient, teacher, monkeypatch):
    def offline(request):
        raise httpx.ConnectError("offline")

    mock, _ = transport(offline)
    monkeypatch.setattr(runtime, "transport", mock)
    connection = connect(client, teacher).json()["connection"]
    assert connection["status"] == "unverified" and "connect" in connection["last_error"].lower()


def test_replacing_and_deleting_a_key(client: TestClient, teacher, stub):
    first = connect(client, teacher).json()["connection"]
    stub.valid_key = "sk-test-second-key-5678"
    second = connect(client, teacher, key="sk-test-second-key-5678").json()["connection"]
    assert first["id"] == second["id"] and second["key_hint"] == "…5678"

    configure_response = client.put("/api/model-configs/evaluator", headers=auth(teacher),
                                    json={"provider": "openai", "model": "gpt-test"})
    assert configure_response.status_code == 200
    assert client.delete(f"/api/providers/{second['id']}", headers=auth(teacher)).status_code == 204
    assert client.get("/api/model-configs", headers=auth(teacher)).json() == []


def test_keys_are_private_and_teacher_only(client: TestClient, teacher, student, stub, make_client):
    key_id = connect(client, teacher).json()["connection"]["id"]
    other = register(make_client(), "teacher")
    assert client.delete(f"/api/providers/{key_id}", headers=auth(other)).status_code == 404
    assert all(p["connection"] is None for p in client.get("/api/providers", headers=auth(other)).json())
    assert client.get("/api/providers", headers=auth(student)).status_code == 403
    assert client.post("/api/providers/connect", headers=auth(student),
                       json={"provider": "openai", "api_key": VALID_KEY}).status_code == 403


def test_custom_endpoints_are_disabled_by_default(client: TestClient, teacher, stub):
    response = client.post("/api/providers/connect", headers=auth(teacher),
                           json={"provider": "custom", "api_key": VALID_KEY, "base_url": "http://localhost:9999/v1"})
    assert response.status_code == 403


def test_model_list_and_retest(client: TestClient, teacher, stub):
    connect(client, teacher)
    models = client.get("/api/providers/models", headers=auth(teacher), params={"provider": "openai"}).json()
    assert [m["id"] for m in models] == ["gpt-test", "gpt-vision"]

    stub.valid_key = "sk-rotated-on-provider-side"
    retest = client.post("/api/providers/test", headers=auth(teacher), json={"provider": "openai"}).json()
    assert retest["connection"]["status"] == "invalid"


# --- Model slots and capability checks -------------------------------------

def test_slot_assignment_and_capability_check(client: TestClient, teacher, stub):
    config = configure(client, teacher, slot="ocr", model="gpt-vision")
    assert config["provider"] == "openai" and config["capabilities"] is None

    stub.replies = ['{"answer": "ready"}', '{"answer": "7"}']
    checked = client.post("/api/model-configs/ocr/check", headers=auth(teacher)).json()
    caps = checked["capabilities"]
    assert caps["available"] is True and caps["text"] and caps["json"] and caps["vision"] is True

    # The vision probe really sent an image.
    vision_request = stub.recorder.json_bodies()[-1]
    assert vision_request["messages"][1]["content"][1]["type"] == "image_url"

    # Changing the model clears the old check.
    changed = client.put("/api/model-configs/ocr", headers=auth(teacher), json={"provider": "openai", "model": "gpt-test"})
    assert changed.json()["capabilities"] is None


def test_slot_requires_a_connected_provider(client: TestClient, teacher, stub):
    response = client.put("/api/model-configs/evaluator", headers=auth(teacher), json={"provider": "gemini", "model": "x"})
    assert response.status_code == 404


# --- Router ----------------------------------------------------------------

class Answer(BaseModel):
    answer: str


def _config(teacher_id: str) -> ModelConfig:
    db = SessionLocal()
    return db.scalar(select(ModelConfig).where(ModelConfig.user_id == uuid.UUID(teacher_id)))


def test_router_retries_transient_errors_and_logs_usage(client: TestClient, teacher, stub):
    configure(client, teacher)
    stub.replies = [httpx.Response(503, text="busy"), httpx.Response(429, json={}), '{"answer": "done"}']
    config = _config(teacher["user"]["id"])
    response = ai_router.call(config, AIRequest(system="s", prompt="p"), ai_router.TaskContext(task="unit"))
    assert response.text == '{"answer": "done"}'

    with SessionLocal() as db:
        logs = db.scalars(select(UsageLog).order_by(UsageLog.created_at)).all()
    assert [(log.success, log.error_code) for log in logs] == [(False, "unavailable"), (False, "rate_limited"), (True, None)]
    assert logs[-1].input_tokens == 11

    report = client.get("/api/usage", headers=auth(teacher)).json()
    assert report["total"] == 3 and report["summary"][0]["failures"] == 2


def test_router_does_not_retry_permanent_errors(client: TestClient, teacher, stub):
    configure(client, teacher)
    stub.replies = [httpx.Response(400, json={"error": {"message": "unknown model"}}), '{"answer": "never"}']
    with pytest.raises(Exception) as caught:
        ai_router.call(_config(teacher["user"]["id"]), AIRequest(system="s", prompt="p"), ai_router.TaskContext(task="unit"))
    assert "unknown model" in str(caught.value) and len(stub.replies) == 1


def test_structured_output_is_validated_and_retried_once(client: TestClient, teacher, stub):
    configure(client, teacher)
    stub.replies = ["not json at all", '```json\n{"answer": "fixed"}\n```']
    parsed, _ = ai_router.call_json(_config(teacher["user"]["id"]), AIRequest(system="s", prompt="p", json_schema={}),
                                    Answer, ai_router.TaskContext(task="unit"))
    assert parsed.answer == "fixed"
    assert "previous answer was rejected" in stub.recorder.json_bodies()[-1]["messages"][1]["content"]

    stub.replies = ['{"wrong": 1}', '{"still": "wrong"}']
    with pytest.raises(AIInvalidResponseError):
        ai_router.call_json(_config(teacher["user"]["id"]), AIRequest(system="s", prompt="p", json_schema={}),
                            Answer, ai_router.TaskContext(task="unit"))
