"""Anthropic Claude through the official Python SDK."""

import base64

import anthropic

from app.providers.base import (
    AIAuthenticationError,
    AIBadRequestError,
    AIInvalidResponseError,
    AIPermissionError,
    AIRateLimitError,
    AIRefusalError,
    AIRequest,
    AIResponse,
    AITimeoutError,
    AIUnavailableError,
    AIUsage,
    ModelInfo,
    ProviderAdapter,
    short_error,
)


class ClaudeAdapter(ProviderAdapter):
    slug = "anthropic"
    display_name = "Anthropic Claude"
    default_base_url = "https://api.anthropic.com"

    def _client(self) -> anthropic.Anthropic:
        http_client = anthropic.DefaultHttpxClient(transport=self.transport) if self.transport else None
        # The router retries transient failures itself, so the SDK does not retry too.
        return anthropic.Anthropic(
            api_key=self.api_key, base_url=self.base_url, timeout=self.timeout, max_retries=0, http_client=http_client
        )

    def _call(self, fn):
        """Run an SDK call, translating SDK errors into provider-neutral ones."""
        try:
            return fn()
        except anthropic.AuthenticationError:
            raise AIAuthenticationError("Anthropic rejected the API key") from None
        except anthropic.PermissionDeniedError as exc:
            raise AIPermissionError(f"Anthropic denied access with this key. {short_error(exc.message)}") from None
        except anthropic.NotFoundError as exc:
            raise AIBadRequestError(f"Anthropic could not find that model. {short_error(exc.message)}") from None
        except anthropic.RateLimitError as exc:
            retry_after = exc.response.headers.get("retry-after") if exc.response is not None else None
            raise AIRateLimitError(
                "Anthropic rate limit reached",
                retry_after=float(retry_after) if retry_after and retry_after.isdigit() else None,
            ) from None
        except anthropic.BadRequestError as exc:
            raise AIBadRequestError(f"Anthropic rejected the request. {short_error(exc.message)}") from None
        except anthropic.APITimeoutError:
            raise AITimeoutError("Anthropic did not respond in time") from None
        except anthropic.APIConnectionError:
            raise AIUnavailableError("Could not connect to Anthropic") from None
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise AIUnavailableError(f"Anthropic is temporarily unavailable ({exc.status_code})") from None
            raise AIBadRequestError(f"Anthropic returned an error ({exc.status_code}). {short_error(exc.message)}") from None

    def complete(self, model: str, request: AIRequest) -> AIResponse:
        content: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image.media_type,
                    "data": base64.standard_b64encode(image.data).decode("ascii"),
                },
            }
            for image in request.images
        ]
        content.append({"type": "text", "text": request.prompt})
        kwargs: dict = {
            "model": model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": content}],
        }
        if request.json_schema is not None:
            # Structured outputs: the text block is guaranteed to be JSON matching the schema.
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": request.json_schema}}

        with self._client() as client:
            message = self._call(lambda: client.messages.create(**kwargs))

        if message.stop_reason == "refusal":
            category = getattr(getattr(message, "stop_details", None), "category", None)
            raise AIRefusalError(f"Claude declined the request{f' ({category})' if category else ''}")
        if message.stop_reason == "max_tokens":
            raise AIInvalidResponseError("The answer was cut off because it reached the output limit")
        text = "".join(block.text for block in message.content if block.type == "text")
        if not text:
            raise AIInvalidResponseError("Claude returned an empty answer")
        return AIResponse(
            text=text,
            model=message.model,
            usage=AIUsage(input_tokens=message.usage.input_tokens, output_tokens=message.usage.output_tokens),
        )

    def list_models(self) -> list[ModelInfo]:
        with self._client() as client:
            items = self._call(lambda: list(client.models.list()))
        models = []
        for item in items:
            capabilities = getattr(item, "capabilities", None)

            def supported(name: str) -> bool | None:
                # Typed object in current SDKs, plain dict in older ones.
                value = capabilities.get(name) if isinstance(capabilities, dict) else getattr(capabilities, name, None)
                if value is None:
                    return None
                flag = value.get("supported") if isinstance(value, dict) else getattr(value, "supported", None)
                return bool(flag) if flag is not None else None

            models.append(ModelInfo(
                id=item.id,
                name=getattr(item, "display_name", None) or item.id,
                context_window=getattr(item, "max_input_tokens", None),
                supports_vision=supported("image_input"),
                supports_json=supported("structured_outputs"),
            ))
        return models
