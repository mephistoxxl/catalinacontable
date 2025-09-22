"""Helper utilities to build normalized media paths for invoices and proformas."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from .storage_io import build_storage_path


@dataclass(frozen=True)
class FacturaMediaPaths:
    """Paths used to persist invoice artefacts."""

    base_dir: str
    xml_dir: str
    pdf_dir: str
    ride_dir: str


@dataclass(frozen=True)
class ProformaMediaPaths:
    """Paths used to persist proforma artefacts."""

    base_dir: str
    pdf_dir: str


def build_factura_media_paths(factura) -> FacturaMediaPaths:
    """Return normalized storage prefixes for an invoice.

    All returned paths are relative to the configured default storage and the
    directories are pre-created (using ``default_storage``) to work with both
    filesystem and remote backends.
    """

    ruc = _extract_ruc(getattr(factura, "empresa", None)) or _extract_ruc(factura)
    base_dir = build_storage_path("facturas", ruc)
    xml_dir = build_storage_path("facturas", ruc, "xml")
    pdf_dir = build_storage_path("facturas", ruc, "pdf")
    ride_dir = build_storage_path("facturas", ruc, "ride")

    for prefix in (base_dir, xml_dir, pdf_dir, ride_dir):
        _ensure_prefix(prefix)

    return FacturaMediaPaths(base_dir=base_dir, xml_dir=xml_dir, pdf_dir=pdf_dir, ride_dir=ride_dir)


def build_proforma_media_paths(proforma) -> ProformaMediaPaths:
    """Return normalized storage prefixes for a proforma."""

    ruc = _extract_ruc(getattr(proforma, "empresa", None)) or _extract_ruc(proforma)
    base_dir = build_storage_path("proformas", ruc)
    pdf_dir = build_storage_path("proformas", ruc, "pdf")

    for prefix in (base_dir, pdf_dir):
        _ensure_prefix(prefix)

    return ProformaMediaPaths(base_dir=base_dir, pdf_dir=pdf_dir)


def _extract_ruc(obj: Optional[object]) -> str:
    """Obtain a RUC/identifier fallback from *obj*."""

    if obj is None:
        return "sin_ruc"

    for attr in ("ruc", "identificacion", "identification", "tax_id"):
        value = getattr(obj, attr, None)
        if value:
            value = str(value).strip()
            if value:
                return value

    return "sin_ruc"


def _ensure_prefix(prefix: str) -> None:
    """Ensure *prefix* exists in the configured storage backend."""

    normalized = prefix.rstrip("/")
    if not normalized:
        return

    placeholder = f"{normalized}/.keep"
    if default_storage.exists(placeholder):
        return

    # Save & remove a placeholder file to ensure the prefix is created without
    # assuming a local filesystem.
    saved_path = default_storage.save(placeholder, ContentFile(b""))
    try:
        default_storage.delete(saved_path)
    except Exception:
        # Best-effort cleanup – in remote storages deleting may not be needed
        # and errors are ignored intentionally.
        pass
