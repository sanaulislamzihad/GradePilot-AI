"""Authenticated encryption (AES-256-GCM) for secrets stored in the database.

Ciphertext format: "<key_id>$<base64 nonce>$<base64 ciphertext+tag>".
The associated data binds a ciphertext to its owner and purpose, so a value
copied into another user's row cannot be decrypted there.
"""

import base64
import binascii
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

_NONCE_BYTES = 12


class EncryptionUnavailableError(Exception):
    """No valid encryption key is configured."""


class DecryptionError(Exception):
    """The value is corrupted, was tampered with, or uses an unknown key."""


@lru_cache
def _keys() -> tuple[str, dict[str, bytes]]:
    raw = get_settings().encryption_keys.strip()
    if not raw:
        raise EncryptionUnavailableError(
            "ENCRYPTION_KEYS is not set. Generate one with: "
            'python -c "import os,base64; print(\'k1:\' + base64.b64encode(os.urandom(32)).decode())"'
        )
    keys: dict[str, bytes] = {}
    active = ""
    for entry in raw.split(","):
        key_id, _, encoded = entry.strip().partition(":")
        try:
            key = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise EncryptionUnavailableError(f"Encryption key {key_id!r} is not valid base64") from None
        if not key_id or "$" in key_id or len(key) != 32:
            raise EncryptionUnavailableError(f"Encryption key {key_id!r} must be a 32-byte key with a simple id")
        keys[key_id] = key
        active = active or key_id
    return active, keys


def is_configured() -> bool:
    try:
        _keys()
        return True
    except EncryptionUnavailableError:
        return False


def encrypt(plaintext: str, associated_data: str) -> str:
    active, keys = _keys()
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(keys[active]).encrypt(nonce, plaintext.encode("utf-8"), associated_data.encode("utf-8"))
    return f"{active}${base64.b64encode(nonce).decode()}${base64.b64encode(ciphertext).decode()}"


def decrypt(token: str, associated_data: str) -> str:
    _, keys = _keys()
    try:
        key_id, nonce_b64, ciphertext_b64 = token.split("$")
        key = keys[key_id]
        nonce = base64.b64decode(nonce_b64, validate=True)
        ciphertext = base64.b64decode(ciphertext_b64, validate=True)
        return AESGCM(key).decrypt(nonce, ciphertext, associated_data.encode("utf-8")).decode("utf-8")
    except (ValueError, KeyError, InvalidTag, binascii.Error):
        raise DecryptionError("Stored secret could not be decrypted") from None


def mask(secret: str) -> str:
    """Show only enough to recognise a key: "…abcd"."""
    return f"…{secret[-4:]}" if len(secret) >= 8 else "…"
