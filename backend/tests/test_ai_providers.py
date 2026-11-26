import base64
import json

import httpx
import httpx2
import pytest

from app.core.config import get_settings
from app.providers.base import (
    AIAuthenticationError,
    AIConfigurationError,
    AIImage,
    AIInvalidResponseError,
    AIRateLimitError,
    AIRefusalError,
    AIRequest,
    AIUnavailableError,
)
from app.providers.claude import ClaudeAdapter
from app.providers.deepseek import DeepSeekAdapter
from app.providers.gemini import GeminiAdapter
from app.providers.openai import OpenAIAdapter
from app.providers.openrouter import OpenRouterAdapter
from app.security import crypto
from tests.ai_mocks import chat_completion, transport, transport2

KEY = "sk-test-secret-key-9876"
SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"], "additionalProperties": False}
IMAGE = AIImage("image/png", b"\x89PNG fake")


def request(**kwargs) -> AIRequest:
    return AIRequest(system="You grade.", prompt="Grade this.", **kwargs)


# --- Encryption ------------------------------------------------------------

def test_encryption_round_trip_and_binding():
    token = crypto.encrypt(KEY, "user_api_key:u1:openai")
    assert KEY not in token and token.startswith("test$")
    assert crypto.decrypt(token, "user_api_key:u1:openai") == KEY
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(token, "user_api_key:u2:openai")  # copied to another user
    key_id, nonce, ciphertext = token.split("$")
    tampered = base64.b64encode(bytes([base64.b64decode(ciphertext)[0] ^ 1]) + base64.b64decode(ciphertext)[1:]).decode()
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(f"{key_id}${nonce}${tampered}", "user_api_key:u1:openai")
    assert crypto.encrypt(KEY, "a") != crypto.encrypt(KEY, "a")  # fresh nonce every time
    assert crypto.mask(KEY) == "…9876"


def test_key_rotation_keeps_old_secrets_readable(monkeypatch):
    old = crypto.encrypt(KEY, "aad")
    monkeypatch.setattr(get_settings(), "encryption_keys", "new:" + "B" * 43 + "=,test:" + "A" * 43 + "=")
    crypto._keys.cache_clear()
    try:
        assert crypto.decrypt(old, "aad") == KEY
        assert crypto.encrypt(KEY, "aad").startswith("new$")
    finally:
        monkeypatch.undo()
        crypto._keys.cache_clear()


def test_adapters_refuse_empty_keys():
    with pytest.raises(AIConfigurationError):
        OpenAIAdapter("  ")


# --- OpenAI-compatible -----------------------------------------------------

def test_openai_request_shape_and_usage():
    mock, recorder = transport(lambda r: httpx.Response(200, json=chat_completion('{"answer": "ok"}')))
    response = OpenAIAdapter(KEY, transport=mock).complete("gpt-test", request(images=[IMAGE], json_schema=SCHEMA))

    sent = recorder.requests[0]
    assert sent.url == "https://api.openai.com/v1/chat/completions"
    assert sent.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(sent.content)
    assert body["model"] == "gpt-test" and body["max_completion_tokens"] == 8000
    assert "temperature" not in body
    assert body["response_format"]["type"] == "json_schema" and body["response_format"]["json_schema"]["strict"] is True
    user_parts = body["messages"][1]["content"]
    assert user_parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert response.text == '{"answer": "ok"}'
    assert (response.usage.input_tokens, response.usage.output_tokens) == (11, 7)


def test_compatible_providers_use_json_object_mode():
    mock, recorder = transport(lambda r: httpx.Response(200, json=chat_completion("{}")))
    DeepSeekAdapter(KEY, transport=mock).complete("deepseek-chat", request(json_schema=SCHEMA))
    body = recorder.json_bodies()[0]
    assert str(recorder.requests[0].url).startswith("https://api.deepseek.com/v1/")
    assert body["response_format"] == {"type": "json_object"} and "max_tokens" in body


def test_openrouter_reports_cost_and_capabilities():
    def handler(r):
        if r.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{
                "id": "vendor/model", "name": "Vendor Model", "context_length": 128000,
                "architecture": {"input_modalities": ["text", "image"]}, "supported_parameters": ["response_format"],
            }]})
        return httpx.Response(200, json=chat_completion("{}", usage={"prompt_tokens": 5, "completion_tokens": 2, "cost": 0.00042}))

    mock, recorder = transport(handler)
    adapter = OpenRouterAdapter(KEY, transport=mock)
    response = adapter.complete("vendor/model", request())
    assert recorder.json_bodies()[0]["usage"] == {"include": True}
    assert str(response.usage.cost_usd) == "0.00042"
    (model,) = adapter.list_models()
    assert (model.context_window, model.supports_vision, model.supports_json) == (128000, True, True)


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(401, json={"error": {"message": "bad key"}}), AIAuthenticationError),
        (httpx.Response(429, headers={"retry-after": "7"}, json={"error": {"message": "slow down"}}), AIRateLimitError),
        (httpx.Response(503, text="upstream down"), AIUnavailableError),
        (httpx.Response(200, json=chat_completion("partial", finish="length")), AIInvalidResponseError),
        (httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"refusal": "no"}}]}), AIRefusalError),
    ],
)
def test_openai_error_mapping(response, error):
    mock, _ = transport(lambda r: response)
    with pytest.raises(error) as caught:
        OpenAIAdapter(KEY, transport=mock).complete("gpt-test", request())
    assert KEY not in caught.value.message
    if error is AIRateLimitError:
        assert caught.value.retry_after == 7.0 and caught.value.retryable


def test_network_failure_is_retryable():
    def boom(r):
        raise httpx.ConnectError("refused")

    mock, _ = transport(boom)
    with pytest.raises(AIUnavailableError) as caught:
        OpenAIAdapter(KEY, transport=mock).complete("m", request())
    assert caught.value.retryable


# --- Gemini ----------------------------------------------------------------

def test_gemini_request_shape_keeps_key_out_of_url():
    reply = {
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"answer": "ok"}'}]}}],
        "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 4},
        "modelVersion": "gemini-test-001",
    }
    mock, recorder = transport(lambda r: httpx.Response(200, json=reply))
    response = GeminiAdapter(KEY, transport=mock).complete("gemini-test", request(images=[IMAGE], json_schema=SCHEMA))

    sent = recorder.requests[0]
    assert sent.url.path == "/v1beta/models/gemini-test:generateContent"
    assert KEY not in str(sent.url) and sent.headers["x-goog-api-key"] == KEY
    body = json.loads(sent.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/png"
    assert response.model == "gemini-test-001" and response.usage.input_tokens == 20


def test_gemini_safety_block_and_model_pagination():
    mock, _ = transport(lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(AIRefusalError):
        GeminiAdapter(KEY, transport=mock).complete("g", request())

    pages = iter([
        {"models": [{"name": "models/a", "supportedGenerationMethods": ["generateContent"], "inputTokenLimit": 100}],
         "nextPageToken": "p2"},
        {"models": [{"name": "models/embed", "supportedGenerationMethods": ["embedContent"]},
                    {"name": "models/b", "supportedGenerationMethods": ["generateContent"]}]},
    ])
    mock, recorder = transport(lambda r: httpx.Response(200, json=next(pages)))
    models = GeminiAdapter(KEY, transport=mock).list_models()
    assert [m.id for m in models] == ["a", "b"]
    assert recorder.requests[1].url.params["pageToken"] == "p2"


# --- Anthropic (official SDK over a mock transport) ------------------------

def _claude_message(text: str, stop_reason: str = "end_turn") -> dict:
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-test",
        "content": [{"type": "text", "text": text}], "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 30, "output_tokens": 9},
    }


def test_claude_request_uses_structured_output_and_images():
    mock, recorder = transport2(lambda r: httpx2.Response(200, json=_claude_message('{"answer": "ok"}')))
    response = ClaudeAdapter(KEY, transport=mock).complete("claude-test", request(images=[IMAGE], json_schema=SCHEMA))

    sent = recorder.requests[0]
    assert sent.url.path == "/v1/messages" and sent.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(sent.content)
    assert body["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMA}}
    assert body["messages"][0]["content"][0]["source"]["type"] == "base64"
    assert body["messages"][0]["content"][-1] == {"type": "text", "text": "Grade this."}
    assert "temperature" not in body
    assert response.text == '{"answer": "ok"}' and response.usage.output_tokens == 9


def test_claude_refusal_and_auth_errors():
    mock, _ = transport2(lambda r: httpx2.Response(200, json=_claude_message("", stop_reason="refusal")))
    with pytest.raises(AIRefusalError):
        ClaudeAdapter(KEY, transport=mock).complete("claude-test", request())

    mock, _ = transport2(lambda r: httpx2.Response(
        401, json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}))
    with pytest.raises(AIAuthenticationError):
        ClaudeAdapter(KEY, transport=mock).complete("claude-test", request())


def test_claude_model_capabilities_come_from_the_models_api():
    page = {
        "data": [{
            "type": "model", "id": "claude-test", "display_name": "Claude Test", "created_at": "2026-01-01T00:00:00Z",
            "max_input_tokens": 1000000, "max_tokens": 128000,
            "capabilities": {"image_input": {"supported": True}, "structured_outputs": {"supported": True}},
        }],
        "has_more": False, "first_id": "claude-test", "last_id": "claude-test",
    }
    mock, _ = transport2(lambda r: httpx2.Response(200, json=page))
    (model,) = ClaudeAdapter(KEY, transport=mock).list_models()
    assert (model.id, model.context_window, model.supports_vision, model.supports_json) == (
        "claude-test", 1000000, True, True)
