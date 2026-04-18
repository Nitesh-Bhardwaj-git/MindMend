"""
encryption.py — Transparent field-level encryption for MindMend.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
The key is read from settings.MINDMEND_ENCRYPTION_KEY.

Usage:
    from .encryption import EncryptedTextField

    class MyModel(models.Model):
        secret = EncryptedTextField()

Behaviour:
  - Values are encrypted before being written to the database.
  - Values are decrypted transparently when read from the database.
  - If a row was stored as plain text (legacy data), decryption falls back
    to returning the original value so nothing breaks on existing data.
  - Empty strings and None are stored as-is (no encryption overhead).
"""

import logging
from django.db import models
from django.conf import settings

logger = logging.getLogger(__name__)

_fernet_instance = None


def _get_fernet():
    """Return a cached Fernet instance built from settings.MINDMEND_ENCRYPTION_KEY."""
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        logger.error(
            "MindMend encryption: 'cryptography' package not installed. "
            "Run: pip install cryptography"
        )
        return None

    key = getattr(settings, 'MINDMEND_ENCRYPTION_KEY', '')
    if not key:
        logger.warning(
            "MindMend encryption: MINDMEND_ENCRYPTION_KEY not set. "
            "Messages will NOT be encrypted. Set this env var for production."
        )
        return None

    try:
        _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet_instance
    except Exception as exc:
        logger.error("MindMend encryption: invalid MINDMEND_ENCRYPTION_KEY — %s", exc)
        return None


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns plaintext unchanged if key is unavailable."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    try:
        return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')
    except Exception as exc:
        logger.error("MindMend encryption: encrypt failed — %s", exc)
        return plaintext


def decrypt_value(ciphertext: str) -> str:
    """
    Decrypt a Fernet-encrypted string.
    Gracefully returns the original value if decryption fails
    (e.g., legacy plain-text rows or key mismatch).
    """
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except Exception:
        # Not a valid Fernet token — treat as plain text (legacy row)
        return ciphertext


class EncryptedTextField(models.TextField):
    """
    A Django TextField that transparently encrypts values before saving
    and decrypts them when reading from the database.

    Inherits from TextField so Django treats the underlying column as TEXT,
    requiring no schema changes when applied to existing fields.
    """

    def from_db_value(self, value, expression, connection):
        """Called every time a value is read from the DB."""
        return decrypt_value(value)

    def to_python(self, value):
        """Called during deserialization and form validation."""
        value = super().to_python(value)
        return decrypt_value(value) if value else value

    def get_prep_value(self, value):
        """Called just before writing to the DB."""
        value = super().get_prep_value(value)
        return encrypt_value(value) if value else value
