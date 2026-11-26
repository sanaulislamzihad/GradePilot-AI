"""Provider-neutral request/response types and errors.

The grading pipeline talks only to these types; each provider module translates
them to and from its own API. Adding a provider means adding one adapter.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


# --- Errors ----------------------------------------------------------------

class AIError(Exception):
    """Base class. `message` is safe to show a teacher; it never contains the API key."""

    code = "provider_error"
    retryable = False

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class AIConfigurationError(AIError):
    code = "not_configured"


class AIAuthenticationError(AIError):
    code = "invalid_key"


class AIPermissionError(AIError):
    code = "permission_denied"


class AIRateLimitError(AIError):
    code = "rate_limited"
    retryable = True


class AITimeoutError(AIError):
    code = "timeout"
    retryable = True


class AIUnavailableError(AIError):
    """Provider-side failure (5xx) or network problem."""

    code = "unavailable"
    retryable = True


class AIBadRequestError(AIError):
    """The provider rejected the request (unknown model, unsupported input, ...)."""

    code = "bad_request"


class AIRefusalError(AIError):
    code = "refused"


class AIInvalidResponseError(AIError):
    """The model answered, but not in a usable form (truncated, not valid JSON, wrong shape)."""

    code = "invalid_response"


# --- Request / response ----------------------------------------------------

@dataclass(frozen=True)
class AIImage:
    media_type: str  # image/png or image/jpeg
    data: bytes


@dataclass
class AIRequest:
    system: str
    prompt: str
    images: list[AIImage] = field(default_factory=list)
    # JSON Schema the answer must follow. Adapters use the provider's native JSON
    # mode where it exists; the router validates the result either way.
    json_schema: dict | None = None
    max_tokens: int = 8000


@dataclass
class AIUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: Decimal | None = None


@dataclass
class AIResponse:
    text: str
    model: str
    usage: AIUsage = field(default_factory=AIUsage)


@dataclass
class ModelInfo:
    id: str
    name: str
    context_window: int | None = None
    # None means the provider does not say; a capability check can find out.
    supports_vision: bool | None = None
    supports_json: bool | None = None


def short_error(text: str | None, limit: int = 300) -> str:
    """Trim provider error text for storage and display."""
    cleaned = " ".join((text or "").split())
    return cleaned[:limit] + ("…" if len(cleaned) > limit else "")


class ProviderAdapter(ABC):
    slug: str
    display_name: str
    default_base_url: str | None = None

    def __init__(self, api_key: str, *, base_url: str | None = None, timeout: float = 120.0, transport=None) -> None:
        if not api_key or not api_key.strip():
            # Never fall back to ambient credentials on the server.
            raise AIConfigurationError("No API key is configured for this provider")
        self.api_key = api_key.strip()
        self.base_url = (base_url or self.default_base_url or "").rstrip("/")
        self.timeout = timeout
        # Tests inject a mock transport; production uses the real network.
        self.transport = transport

    @abstractmethod
    def complete(self, model: str, request: AIRequest) -> AIResponse: ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]: ...

    def test_connection(self) -> None:
        """Raise an AIError if the key does not work. Listing models costs no tokens."""
        self.list_models()
