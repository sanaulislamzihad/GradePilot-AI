"""OpenAI Chat Completions, and the shared base for OpenAI-compatible APIs."""

import base64
from decimal import Decimal, InvalidOperation

from app.providers import http
from app.providers.base import (
    AIImage,
    AIInvalidResponseError,
    AIRefusalError,
    AIRequest,
    AIResponse,
    AIUsage,
    ModelInfo,
    ProviderAdapter,
)


def _image_part(image: AIImage) -> dict:
    encoded = base64.b64encode(image.data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{image.media_type};base64,{encoded}"}}


class OpenAICompatibleAdapter(ProviderAdapter):
    """Chat Completions API as implemented by OpenAI and compatible providers."""

    slug = "openai"
    display_name = "OpenAI"
    default_base_url = "https://api.openai.com/v1"
    # "json_schema" (strict schema) where supported, else "json_object".
    json_mode = "json_schema"
    max_tokens_field = "max_completion_tokens"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _payload(self, model: str, request: AIRequest) -> dict:
        content: list[dict] = [{"type": "text", "text": request.prompt}]
        content.extend(_image_part(image) for image in request.images)
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": content if request.images else request.prompt},
            ],
            self.max_tokens_field: request.max_tokens,
        }
        if request.json_schema is not None:
            if self.json_mode == "json_schema":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "result", "schema": request.json_schema, "strict": True},
                }
            else:
                payload["response_format"] = {"type": "json_object"}
        return payload

    def _usage(self, body: dict) -> AIUsage:
        usage = body.get("usage") or {}
        cost = None
        if usage.get("cost") is not None:
            try:
                cost = Decimal(str(usage["cost"]))
            except InvalidOperation:
                cost = None
        return AIUsage(
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            cost_usd=cost,
        )

    def complete(self, model: str, request: AIRequest) -> AIResponse:
        with http.client(self.timeout, self.transport) as client:
            body = http.send(client, "POST", f"{self.base_url}/chat/completions", self.display_name,
                             headers=self._headers(), json=self._payload(model, request))
        choices = body.get("choices") or []
        if not choices:
            raise AIInvalidResponseError(f"{self.display_name} returned no answer")
        choice = choices[0]
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise AIRefusalError(f"The model declined the request: {message['refusal']}")
        if choice.get("finish_reason") == "length":
            raise AIInvalidResponseError("The answer was cut off because it reached the output limit")
        text = message.get("content")
        if isinstance(text, list):  # some compatible servers return content parts
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
        if not text:
            raise AIInvalidResponseError(f"{self.display_name} returned an empty answer")
        return AIResponse(text=text, model=body.get("model") or model, usage=self._usage(body))

    def _model_info(self, item: dict) -> ModelInfo:
        return ModelInfo(id=item["id"], name=item.get("name") or item["id"],
                         context_window=item.get("context_window") or item.get("context_length"))

    def list_models(self) -> list[ModelInfo]:
        with http.client(self.timeout, self.transport) as client:
            body = http.send(client, "GET", f"{self.base_url}/models", self.display_name, headers=self._headers())
        items = body.get("data") or []
        models = [self._model_info(item) for item in items if isinstance(item, dict) and item.get("id")]
        return sorted(models, key=lambda m: m.id)


class OpenAIAdapter(OpenAICompatibleAdapter):
    pass
