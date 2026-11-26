"""Google Gemini (Generative Language API, v1beta)."""

import base64

from app.providers import http
from app.providers.base import (
    AIInvalidResponseError,
    AIRefusalError,
    AIRequest,
    AIResponse,
    AIUsage,
    ModelInfo,
    ProviderAdapter,
)


class GeminiAdapter(ProviderAdapter):
    slug = "gemini"
    display_name = "Google Gemini"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _headers(self) -> dict:
        # Header rather than ?key= so the key never appears in URLs or access logs.
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    @staticmethod
    def _model_path(model: str) -> str:
        return model if model.startswith("models/") else f"models/{model}"

    def complete(self, model: str, request: AIRequest) -> AIResponse:
        parts: list[dict] = [{"text": request.prompt}]
        parts.extend(
            {"inline_data": {"mime_type": image.media_type, "data": base64.b64encode(image.data).decode("ascii")}}
            for image in request.images
        )
        payload: dict = {
            "systemInstruction": {"parts": [{"text": request.system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"maxOutputTokens": request.max_tokens},
        }
        if request.json_schema is not None:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        with http.client(self.timeout, self.transport) as client:
            body = http.send(client, "POST", f"{self.base_url}/{self._model_path(model)}:generateContent",
                             self.display_name, headers=self._headers(), json=payload)

        feedback = body.get("promptFeedback") or {}
        if feedback.get("blockReason"):
            raise AIRefusalError(f"Gemini blocked the request ({feedback['blockReason']})")
        candidates = body.get("candidates") or []
        if not candidates:
            raise AIInvalidResponseError("Gemini returned no answer")
        candidate = candidates[0]
        finish = candidate.get("finishReason")
        if finish in ("SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
            raise AIRefusalError(f"Gemini stopped the answer ({finish})")
        if finish == "MAX_TOKENS":
            raise AIInvalidResponseError("The answer was cut off because it reached the output limit")
        text = "".join(part.get("text", "") for part in (candidate.get("content") or {}).get("parts", []))
        if not text:
            raise AIInvalidResponseError("Gemini returned an empty answer")
        usage = body.get("usageMetadata") or {}
        return AIResponse(
            text=text,
            model=body.get("modelVersion") or model,
            usage=AIUsage(input_tokens=usage.get("promptTokenCount"), output_tokens=usage.get("candidatesTokenCount")),
        )

    def list_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        page_token = None
        with http.client(self.timeout, self.transport) as client:
            for _ in range(10):  # follow pagination, with a safety bound
                params = {"pageSize": 1000, **({"pageToken": page_token} if page_token else {})}
                body = http.send(client, "GET", f"{self.base_url}/models", self.display_name,
                                 headers=self._headers(), params=params)
                for item in body.get("models") or []:
                    if "generateContent" not in (item.get("supportedGenerationMethods") or []):
                        continue
                    models.append(ModelInfo(
                        id=item["name"].removeprefix("models/"),
                        name=item.get("displayName") or item["name"],
                        context_window=item.get("inputTokenLimit"),
                    ))
                page_token = body.get("nextPageToken")
                if not page_token:
                    break
        return sorted(models, key=lambda m: m.id)
