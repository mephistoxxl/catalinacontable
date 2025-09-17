from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.core.files.base import ContentFile
from cryptography.fernet import Fernet
import os
import warnings

class EncryptedFirmaStorage(FileSystemStorage):
    """Storage para guardar archivos de firma electrónica cifrados.

    Los archivos se almacenan en ``settings.FIRMAS_ROOT`` y se cifran usando
    ``Fernet`` con la clave definida en ``settings.FIRMAS_KEY``.
    """

    def __init__(self, *args, **kwargs):
        location = getattr(settings, "FIRMAS_ROOT", os.path.join(settings.BASE_DIR, "firmas_secure"))
        super().__init__(location=location, *args, **kwargs)

    def _encrypt(self, data: bytes) -> bytes:
        """Cifra los datos si existe ``settings.FIRMAS_KEY``; de lo contrario retorna sin cambios."""
        if getattr(settings, 'FIRMAS_KEY', None) is None:
            return data  # modo sin cifrado
        f = Fernet(settings.FIRMAS_KEY)
        return f.encrypt(data)

    def _decrypt(self, data: bytes) -> bytes:
        """Descifra los datos solo si hay clave; si no, retorna los datos originales."""
        if getattr(settings, 'FIRMAS_KEY', None) is None:
            return data
        f = Fernet(settings.FIRMAS_KEY)
        return f.decrypt(data)

    def _save(self, name, content):
        # Leer datos en memoria para cifrarlos antes de guardar (si aplica)
        raw = content.read()
        processed = self._encrypt(raw)
        final_content = ContentFile(processed)
        return super()._save(name, final_content)

    def open(self, name, mode='rb'):
        # Abrir el archivo (cifrado o plano) y devolverlo descifrado si aplica
        with super().open(name, 'rb') as stored_file:
            data = stored_file.read()
        decrypted = self._decrypt(data)
        return ContentFile(decrypted)
