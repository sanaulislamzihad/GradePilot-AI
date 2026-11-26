"""Mock provider HTTP APIs for tests. No real network calls, no real API keys."""

import json
from collections.abc import Callable

import httpx
import httpx2

Handler = Callable[[httpx.Request], httpx.Response]


class Recorder:
    """Collects requests and answers them from a queue or a function."""

    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def __call__(self, request):
        self.requests.append(request)
        return self.handler(request)

    def json_bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.content]


def transport(handler: Handler) -> tuple[httpx.MockTransport, Recorder]:
    recorder = Recorder(handler)
    return httpx.MockTransport(recorder), recorder


def transport2(handler) -> tuple[httpx2.MockTransport, Recorder]:
    """httpx2 transport, used by the Anthropic SDK."""
    recorder = Recorder(handler)
    return httpx2.MockTransport(recorder), recorder


def chat_completion(content: str, *, finish: str = "stop", usage: dict | None = None, model: str = "test-model") -> dict:
    return {
        "id": "cmpl-1",
        "model": model,
        "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": content}}],
        "usage": usage or {"prompt_tokens": 11, "completion_tokens": 7},
    }


def models_list(*ids: str) -> dict:
    return {"object": "list", "data": [{"id": i, "object": "model"} for i in ids]}


class OpenAIStub:
    """A minimal OpenAI-compatible server: GET /models and POST /chat/completions.

    `replies` is consumed in order for chat requests; a callable reply receives
    the parsed request body.
    """

    def __init__(self, replies=None, models=("test-model",), valid_key="sk-test-valid-key-1234") -> None:
        self.replies = list(replies or [])
        self.models = models
        self.valid_key = valid_key

    def __call__(self, request):
        if request.headers.get("authorization") != f"Bearer {self.valid_key}":
            return httpx.Response(401, json={"error": {"message": "Incorrect API key provided"}})
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=models_list(*self.models))
        body = json.loads(request.content)
        if not self.replies:
            return httpx.Response(500, json={"error": {"message": "no reply queued"}})
        reply = self.replies.pop(0)
        if callable(reply):
            reply = reply(body)
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, json=chat_completion(reply if isinstance(reply, str) else json.dumps(reply)))
