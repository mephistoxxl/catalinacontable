from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.core.files.base import ContentFile
from cryptography.fernet import Fernet
import os

class EncryptedFirmaStorage(FileSystemStorage):
    """Storage para guardar archivos de firma electrónica cifrados.

    Los archivos se almacenan en ``settings.FIRMAS_ROOT`` y se cifran usando
    ``Fernet`` con la clave definida en ``settings.FIRMAS_KEY``.
    """

    def __init__(self, *args, **kwargs):
        location = getattr(settings, "FIRMAS_ROOT", os.path.join(settings.BASE_DIR, "firmas_secure"))
        super().__init__(location=location, *args, **kwargs)

    def _encrypt(self, data: bytes) -> bytes:
        f = Fernet(settings.FIRMAS_KEY)
        return f.encrypt(data)

    def _decrypt(self, data: bytes) -> bytes:
        f = Fernet(settings.FIRMAS_KEY)
        return f.decrypt(data)

    def _save(self, name, content):
        # Leer datos en memoria para cifrarlos antes de guardar
        raw = content.read()
        encrypted = self._encrypt(raw)
        encrypted_content = ContentFile(encrypted)
        return super()._save(name, encrypted_content)

    def open(self, name, mode='rb'):
        # Abrir el archivo cifrado y devolverlo descifrado en memoria
        with super().open(name, 'rb') as encrypted_file:
            encrypted = encrypted_file.read()
        decrypted = self._decrypt(encrypted)
        return ContentFile(decrypted)
