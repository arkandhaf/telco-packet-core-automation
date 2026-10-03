"""
Backward compatibility bridge for src.encrypt_tool.
Canonical implementation now lives in core.transports.crypto.
"""
from core.transports.crypto import encrypt_password, decrypt_password

__all__ = ["encrypt_password", "decrypt_password"]