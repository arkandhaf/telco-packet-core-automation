"""Fernet credential encryption; failures never downgrade to plaintext."""
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()


def _get_fernet_cipher(key: Optional[str]) -> Fernet:
    if not key:
        raise ValueError("SECRET_KEY must be a Fernet key generated with Fernet.generate_key()")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("SECRET_KEY must be a valid Fernet key; passphrase derivation is no longer supported") from exc


def encrypt_password(plain_password: str) -> str:
    if not plain_password:
        return ""
    return _get_fernet_cipher(os.getenv("SECRET_KEY")).encrypt(plain_password.encode("utf-8")).decode("ascii")


def decrypt_password(encrypted_password: str) -> str:
    if not encrypted_password:
        return ""
    # Legacy plaintext requires explicit opt-in. A damaged token never qualifies.
    if not encrypted_password.startswith("gAAAA"):
        if os.getenv("RELPOOL_ALLOW_PLAINTEXT_PASSWORD", "").lower() == "true":
            return encrypted_password
        raise ValueError("Password must be encrypted, or plaintext must be explicitly enabled")
    try:
        return _get_fernet_cipher(os.getenv("SECRET_KEY")).decrypt(encrypted_password.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError) as exc:
        raise ValueError("Unable to decrypt SSH credential; check SECRET_KEY and stored token") from exc