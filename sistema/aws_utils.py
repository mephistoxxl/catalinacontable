"""Utilidades relacionadas con AWS S3 (URLs prefirmadas, etc.)."""

from __future__ import annotations

import logging
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def build_presigned_media_url(key: Optional[str], *, expires_in: Optional[int] = None) -> Optional[str]:
    """Genera una URL firmada para archivos en el bucket S3 configurado.

    Si el almacenamiento remoto no está habilitado, retorna la URL local.
    Cuando no es posible firmar (por ejemplo, en entornos de prueba sin S3),
    se retorna ``None`` para que la vista pueda aplicar un fallback seguro.
    """

    if not key:
        return None

    if not getattr(settings, "USE_REMOTE_MEDIA_STORAGE", False):
        try:
            return default_storage.url(key)
        except Exception:  # pragma: no cover - solo para entornos sin storage configurado
            base_url = getattr(settings, "MEDIA_URL", "").rstrip("/")
            return f"{base_url}/{key}" if base_url else None

    ttl = expires_in or getattr(settings, "AWS_S3_PRESIGNED_TTL", 3600)

    session = boto3.session.Session()
    client_kwargs = {}

    region = getattr(settings, "AWS_S3_REGION_NAME", None)
    if region:
        client_kwargs["region_name"] = region

    endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url

    signature_version = getattr(settings, "AWS_S3_SIGNATURE_VERSION", None)
    if signature_version:
        client_kwargs["config"] = Config(signature_version=signature_version)

    access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key

    try:
        client = session.client("s3", **client_kwargs)
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": key,
            },
            ExpiresIn=ttl,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.warning("No se pudo generar URL prefirmada para %s: %s", key, exc)
        return None


def build_storage_url_or_none(field) -> Optional[str]:
    """Conveniencia para obtener la URL firmada desde un campo de archivo."""

    if not field:
        return None

    key = getattr(field, "name", None)
    signed_url = build_presigned_media_url(key)
    if signed_url:
        return signed_url

    # Fallback a la URL que expone el storage (puede ya estar firmada).
    try:
        return field.url
    except Exception:  # pragma: no cover - solo entornos sin storage
        return None
