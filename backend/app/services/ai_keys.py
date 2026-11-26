"""Storing, testing and using a user's provider API keys.

The plaintext key exists only in memory for the duration of one request to the
provider. It is never logged, returned to the browser, or stored unencrypted.
"""

import ipaddress
import uuid
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.database.base import utcnow
from app.models.ai import AIProvider, KeyStatus, UserApiKey
from app.models.user import User
from app.providers import ADAPTERS
from app.providers import runtime
from app.providers.base import AIAuthenticationError, AIError, AIPermissionError, ProviderAdapter
from app.security import crypto


def _aad(user_id: uuid.UUID, provider_slug: str) -> str:
    return f"user_api_key:{user_id}:{provider_slug}"


def require_encryption() -> None:
    if not crypto.is_configured():
        raise AppError(503, "API key storage is not configured on the server (ENCRYPTION_KEYS). Contact an administrator.")


def get_provider(db: Session, slug: str) -> AIProvider:
    provider = db.scalar(select(AIProvider).where(AIProvider.slug == slug))
    if provider is None or not provider.is_enabled or slug not in ADAPTERS:
        raise AppError(404, "Unknown AI provider")
    if slug == "custom" and not get_settings().allow_custom_ai_endpoints:
        raise AppError(403, "Custom endpoints are disabled on this server")
    return provider


def validate_base_url(url: str | None) -> str:
    if not url:
        raise AppError(422, "Enter the base URL of the endpoint, for example http://localhost:11434/v1")
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise AppError(422, "The base URL must be an http(s) URL without credentials")
    try:
        if ipaddress.ip_address(parsed.hostname).is_link_local:
            # Cloud metadata services live on link-local addresses.
            raise AppError(422, "Link-local addresses are not allowed")
    except ValueError:
        pass
    return url.strip().rstrip("/")


def adapter_for(key: UserApiKey) -> ProviderAdapter:
    """Build an adapter with the decrypted key. Use it immediately and let it go."""
    slug = key.provider.slug
    if slug == "custom" and not get_settings().allow_custom_ai_endpoints:
        raise AppError(403, "Custom endpoints are disabled on this server")
    secret = crypto.decrypt(key.encrypted_key, _aad(key.user_id, slug))
    return ADAPTERS[slug](
        secret, base_url=key.base_url, timeout=get_settings().ai_request_timeout_seconds, transport=runtime.transport
    )


def save_key(db: Session, user: User, provider: AIProvider, api_key: str, base_url: str | None) -> UserApiKey:
    """Test the key with the provider, then store it encrypted.

    A key the provider explicitly rejects is not saved. If the test cannot
    complete (network, rate limit), the key is saved as unverified.
    """
    require_encryption()
    api_key = api_key.strip()
    if provider.slug == "custom":
        base_url = validate_base_url(base_url)
    else:
        base_url = None

    adapter = ADAPTERS[provider.slug](
        api_key, base_url=base_url, timeout=get_settings().ai_request_timeout_seconds, transport=runtime.transport
    )
    status, error = KeyStatus.VALID, None
    try:
        adapter.test_connection()
    except (AIAuthenticationError, AIPermissionError) as exc:
        raise AppError(400, exc.message) from None
    except AIError as exc:
        status, error = KeyStatus.UNVERIFIED, exc.message

    record = db.scalar(select(UserApiKey).where(UserApiKey.user_id == user.id, UserApiKey.provider_id == provider.id))
    if record is None:
        record = UserApiKey(user_id=user.id, provider_id=provider.id)
        db.add(record)
    record.provider = provider
    record.encrypted_key = crypto.encrypt(api_key, _aad(user.id, provider.slug))
    record.key_hint = crypto.mask(api_key)
    record.base_url = base_url
    record.status = status.value
    record.last_tested_at = utcnow()
    record.last_error = error
    return record


def test_key(key: UserApiKey) -> None:
    """Re-test a stored key and record the outcome on the row."""
    try:
        adapter_for(key).test_connection()
        key.status, key.last_error = KeyStatus.VALID.value, None
    except (AIAuthenticationError, AIPermissionError) as exc:
        key.status, key.last_error = KeyStatus.INVALID.value, exc.message
    except AIError as exc:
        key.status, key.last_error = KeyStatus.UNVERIFIED.value, exc.message
    except crypto.DecryptionError:
        key.status, key.last_error = KeyStatus.INVALID.value, "The stored key could not be decrypted. Enter it again."
    key.last_tested_at = utcnow()


def owned_key(db: Session, user: User, key_id: uuid.UUID) -> UserApiKey:
    key = db.get(UserApiKey, key_id)
    if key is None or key.user_id != user.id:
        raise AppError(404, "Provider connection not found")
    return key


def key_for_provider(db: Session, user: User, slug: str) -> UserApiKey:
    key = db.scalar(
        select(UserApiKey).join(AIProvider).where(UserApiKey.user_id == user.id, AIProvider.slug == slug)
    )
    if key is None:
        raise AppError(404, "Connect this provider first")
    return key
