from app.providers.base import AIRequest, ModelInfo
from app.providers.openai import OpenAICompatibleAdapter


class OpenRouterAdapter(OpenAICompatibleAdapter):
    slug = "openrouter"
    display_name = "OpenRouter"
    default_base_url = "https://openrouter.ai/api/v1"
    # Routed models differ in JSON Schema support; JSON object mode is broadly accepted.
    json_mode = "json_object"
    max_tokens_field = "max_tokens"

    def _payload(self, model: str, request: AIRequest) -> dict:
        payload = super()._payload(model, request)
        # Ask OpenRouter to report the cost of each request.
        payload["usage"] = {"include": True}
        return payload

    def _model_info(self, item: dict) -> ModelInfo:
        modalities = (item.get("architecture") or {}).get("input_modalities")
        params = item.get("supported_parameters")
        return ModelInfo(
            id=item["id"],
            name=item.get("name") or item["id"],
            context_window=item.get("context_length"),
            supports_vision=("image" in modalities) if isinstance(modalities, list) else None,
            supports_json=("response_format" in params) if isinstance(params, list) else None,
        )
