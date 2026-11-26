"""Shared HTTP helpers for adapters that call REST APIs with httpx."""

import httpx

from app.providers.base import (
    AIAuthenticationError,
    AIBadRequestError,
    AIError,
    AIPermissionError,
    AIRateLimitError,
    AITimeoutError,
    AIUnavailableError,
    short_error,
)


def client(timeout: float, transport=None) -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0), transport=transport, follow_redirects=False)


def _provider_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return short_error(response.text)
    error = body.get("error", body) if isinstance(body, dict) else body
    if isinstance(error, dict):
        return short_error(str(error.get("message") or error.get("detail") or error))
    return short_error(str(error))


def raise_for_status(response: httpx.Response, provider: str) -> None:
    if response.is_success:
        return
    status = response.status_code
    detail = _provider_message(response)
    if status == 401:
        raise AIAuthenticationError(f"{provider} rejected the API key. {detail}".strip())
    if status == 403:
        raise AIPermissionError(f"{provider} denied access with this key. {detail}".strip())
    if status == 429:
        retry_after = response.headers.get("retry-after")
        raise AIRateLimitError(
            f"{provider} rate limit or quota reached. {detail}".strip(),
            retry_after=float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else None,
        )
    if status in (408, 504):
        raise AITimeoutError(f"{provider} timed out")
    if status >= 500:
        raise AIUnavailableError(f"{provider} is temporarily unavailable ({status}). {detail}".strip())
    raise AIBadRequestError(f"{provider} rejected the request ({status}). {detail}".strip())


def send(http: httpx.Client, method: str, url: str, provider: str, **kwargs) -> dict:
    try:
        response = http.request(method, url, **kwargs)
    except httpx.TimeoutException:
        raise AITimeoutError(f"{provider} did not respond in time") from None
    except httpx.TransportError:
        raise AIUnavailableError(f"Could not connect to {provider}") from None
    raise_for_status(response, provider)
    try:
        return response.json()
    except ValueError:
        raise AIUnavailableError(f"{provider} returned a response that is not JSON") from None


__all__ = ["AIError", "client", "raise_for_status", "send"]
