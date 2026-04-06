from __future__ import annotations

import hashlib
import hmac
import secrets


def hash_password(password: str, pepper: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", (password + pepper).encode("utf-8"), salt, 200_000
    )
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored_value: str, pepper: str) -> bool:
    try:
        salt_hex, hash_hex = stored_value.split(":", maxsplit=1)
    except ValueError:
        return False

    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    actual = hashlib.pbkdf2_hmac(
        "sha256", (password + pepper).encode("utf-8"), salt, 200_000
    )
    return hmac.compare_digest(actual, expected)


def create_session_token() -> str:
    return secrets.token_urlsafe(32)
