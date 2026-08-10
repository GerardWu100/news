"""Hash and verify browser login passwords with PBKDF2.

PBKDF2 (Password-Based Key Derivation Function 2) turns a password into a
fixed-length key by repeating a keyed hash many times. The repetition is the
point: it makes each guess expensive for someone who steals the stored value.

Stored format
-------------
``pbkdf2_sha256$<iterations>$<salt>$<derived key>`` where the salt and derived
key are URL-safe base64 without padding. The salt is a random value stored in
the clear; it makes two identical passwords hash to different values, so a
precomputed table of common password hashes is useless.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import secrets

PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
MINIMUM_PBKDF2_ITERATIONS = 100_000
MAXIMUM_PBKDF2_ITERATIONS = 1_000_000
SALT_BYTES = 16
MINIMUM_SALT_BYTES = 8
MAXIMUM_SALT_BYTES = 64
SHA256_BYTES = 32


def _b64encode(raw_bytes: bytes) -> str:
    """Encode bytes as URL-safe base64 without trailing padding."""
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")


def _b64decode(raw_text: str) -> bytes:
    """Decode URL-safe base64 text that may omit trailing padding."""
    padding = "=" * (-len(raw_text) % 4)
    return base64.urlsafe_b64decode(raw_text + padding)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Hash a plain-text password for storage.

    Parameters
    ----------
    password : str
        Plain-text password that should be protected at rest.
    salt : bytes | None, optional
        Explicit salt. ``None`` draws a fresh random salt; tests pass a fixed
        value when they need a reproducible hash.

    Returns
    -------
    str
        Serialized hash in the format ``pbkdf2_sha256$iterations$salt$hash``.

    Raises
    ------
    ValueError
        If the password is blank or contains only whitespace.
    """
    if not password.strip():
        raise ValueError("Password must not be blank.")

    salt_bytes = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS,
    )
    return (
        f"{PASSWORD_HASH_SCHEME}${PBKDF2_ITERATIONS}"
        f"${_b64encode(salt_bytes)}${_b64encode(derived_key)}"
    )


def is_password_hash(stored_value: str) -> bool:
    """Return ``True`` for values shaped like :func:`hash_password` output."""
    parts = stored_value.split("$")
    if len(parts) != 4:
        return False
    scheme, iterations_text, salt_text, hash_text = parts
    if scheme != PASSWORD_HASH_SCHEME:
        return False
    if not iterations_text.isdigit():
        return False
    return bool(salt_text and hash_text)


def verify_password(password: str, stored_value: str) -> bool:
    """Check a submitted password against a serialized PBKDF2 hash.

    Parameters
    ----------
    password : str
        Password submitted by the operator.
    stored_value : str
        Serialized hash read from disk. Anything that is not a valid
        ``pbkdf2_sha256$...`` value is rejected instead of raising.

    Returns
    -------
    bool
        ``True`` only when the password reproduces the stored derived key.
    """
    if not is_password_hash(stored_value):
        return False

    try:
        _, iterations_text, salt_text, expected_hash_text = stored_value.split("$", 3)
        iterations = int(iterations_text)
        if not MINIMUM_PBKDF2_ITERATIONS <= iterations <= MAXIMUM_PBKDF2_ITERATIONS:
            # Reject weak hashes, and reject corrupted values whose iteration
            # count would otherwise demand unbounded work during one login.
            return False
        salt_bytes = _b64decode(salt_text)
        expected_hash = _b64decode(expected_hash_text)
    except (ValueError, binascii.Error):
        return False

    if not MINIMUM_SALT_BYTES <= len(salt_bytes) <= MAXIMUM_SALT_BYTES:
        return False
    if len(expected_hash) != SHA256_BYTES:
        return False

    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        iterations,
    )
    # compare_digest takes the same time for every wrong value, so a caller
    # cannot learn the correct hash one byte at a time from response timing.
    return secrets.compare_digest(candidate_hash, expected_hash)
