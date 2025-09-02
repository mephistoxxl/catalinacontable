import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def _get_fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    """Encrypts a string using Fernet."""
    if value is None:
        return None
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypts a previously encrypted string."""
    if token is None:
        return None
    f = _get_fernet()
    return f.decrypt(token.encode()).decode()


class EncryptedCharField(models.CharField):
    """CharField that transparently encrypts/decrypts values using Fernet."""

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ""):
            return value
        return encrypt(value)

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        try:
            return decrypt(value)
        except Exception:
            return value

    def to_python(self, value):
        value = super().to_python(value)
        if value in (None, ""):
            return value
        try:
            return decrypt(value)
        except Exception:
            return value

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        path = "inventario.crypto_utils.EncryptedCharField"
        return name, path, args, kwargs
