import os
import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from .storage import EncryptedFirmaStorage

pytestmark = pytest.mark.django_db

TEST_DATA = b"contenido-de-prueba-firma"


def test_storage_plain_when_no_key(settings, tmp_path, monkeypatch):
    """Cuando FIRMAS_KEY es None, el archivo debe guardarse en texto plano."""
    monkeypatch.setattr(settings, 'FIRMAS_KEY', None)
    storage = EncryptedFirmaStorage()
    name = storage.save('firmas/test_plain.p12', ContentFile(TEST_DATA))
    # Leer directamente el archivo en disco
    disk_path = storage.path(name)
    with open(disk_path, 'rb') as f:
        raw = f.read()
    assert raw == TEST_DATA, 'El archivo debería almacenarse sin cifrar cuando no hay clave'
    # La API open debe devolver el mismo contenido
    with storage.open(name, 'rb') as f:
        assert f.read() == TEST_DATA


def test_storage_encrypted_when_key(settings, tmp_path, monkeypatch):
    """Cuando existe FIRMAS_KEY válida, el archivo debe guardarse cifrado (distinto del original)."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    monkeypatch.setattr(settings, 'FIRMAS_KEY', key)
    storage = EncryptedFirmaStorage()
    name = storage.save('firmas/test_enc.p12', ContentFile(TEST_DATA))
    disk_path = storage.path(name)
    with open(disk_path, 'rb') as f:
        raw = f.read()
    assert raw != TEST_DATA, 'El archivo debe estar cifrado en disco'
    # Abrir vía API debe devolver original
    with storage.open(name, 'rb') as f:
        assert f.read() == TEST_DATA
