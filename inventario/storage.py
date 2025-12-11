from django.core.files.base import ContentFile
from django.core.files.storage import Storage, FileSystemStorage, default_storage
from django.conf import settings
from cryptography.fernet import Fernet
import os


class EncryptedFirmaStorage(Storage):
    """Storage para guardar archivos de firma electrónica cifrados.

    Utiliza el backend de almacenamiento configurado globalmente (por ejemplo,
    S3 mediante ``django-storages``). En entornos locales cae
    automáticamente a ``FileSystemStorage`` utilizando ``FIRMAS_ROOT``.
    """

    def __init__(self, base_storage: Storage | None = None, location: str | None = None):
        # ✅ CORREGIDO: Usar S3 en producción (Heroku) - el filesystem es efímero
        # Las firmas se perdían cada vez que el dyno se reiniciaba (~24h)
        self._use_remote = getattr(settings, "USE_REMOTE_MEDIA_STORAGE", False)

        if base_storage is not None:
            self._storage = base_storage
        elif self._use_remote:
            self._storage = default_storage
        else:
            fs_location = location or getattr(
                settings, "FIRMAS_ROOT", os.path.join(settings.BASE_DIR, "firmas_secure")
            )
            self._storage = FileSystemStorage(location=fs_location)

        self._prefix = ""
        if self._use_remote:
            prefix = location or getattr(settings, "FIRMAS_STORAGE_PREFIX", "")
            self._prefix = str(prefix).strip("/")

    def __getattr__(self, attr):
        """Delegar atributos no definidos a ``self._storage``."""

        return getattr(self._storage, attr)

    @property
    def encryption_enabled(self) -> bool:
        return getattr(settings, 'FIRMAS_KEY', None) is not None

    @property
    def using_remote_storage(self) -> bool:
        return self._use_remote

    def validate_configuration(self) -> list[str]:
        """Devuelve una lista de errores de configuración detectados."""

        errors: list[str] = []
        if not self.using_remote_storage:
            errors.append('El almacenamiento remoto no está activo (USE_REMOTE_MEDIA_STORAGE=False).')

        if not self.encryption_enabled:
            errors.append('FIRMAS_KEY no está configurada; los archivos se almacenarían sin cifrar.')
        else:
            try:
                probe = self._encrypt(b'health-check')
                if probe == b'health-check':
                    errors.append('La clave de cifrado no se está aplicando al guardar archivos.')
            except Exception as exc:  # pragma: no cover - solo diagnóstico
                errors.append(f'No se pudo cifrar datos de prueba: {exc}')

        if self.using_remote_storage and not self._prefix:
            errors.append('FIRMAS_STORAGE_PREFIX no está definido; los certificados compartirían la raíz del bucket.')

        return errors

    def _encrypt(self, data: bytes) -> bytes:
        if getattr(settings, 'FIRMAS_KEY', None) is None:
            return data
        f = Fernet(settings.FIRMAS_KEY)
        return f.encrypt(data)

    def _decrypt(self, data: bytes) -> bytes:
        if getattr(settings, 'FIRMAS_KEY', None) is None:
            return data
        f = Fernet(settings.FIRMAS_KEY)
        return f.decrypt(data)

    def _full_name(self, name: str) -> str:
        normalized = name.replace('\\', '/').lstrip('/')
        if self._prefix:
            if normalized.startswith(f"{self._prefix}/"):
                return normalized
            return f"{self._prefix}/{normalized}"
        return normalized

    def _save(self, name, content):
        raw = content.read()
        processed = self._encrypt(raw)
        final_content = ContentFile(processed)
        storage_name = self._full_name(name)
        if self._storage.exists(storage_name):
            self._storage.delete(storage_name)
        saved_name = self._storage.save(storage_name, final_content)
        return saved_name

    def _open(self, name, mode='rb'):
        storage_name = self._full_name(name)
        with self._storage.open(storage_name, 'rb') as stored_file:
            data = stored_file.read()
        decrypted = self._decrypt(data)
        file_obj = ContentFile(decrypted)
        file_obj.name = os.path.basename(name)
        return file_obj

    def delete(self, name):
        self._storage.delete(self._full_name(name))

    def exists(self, name):
        return self._storage.exists(self._full_name(name))

    def url(self, name):
        return self._storage.url(self._full_name(name))
