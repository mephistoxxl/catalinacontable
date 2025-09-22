"""Utilities to interact with the configured Django storage backend.

These helpers abstract away the differences between local filesystem
storages and remote backends (such as S3 via ``django-storages``) so the
rest of the codebase can remain agnostic about where the files live.
"""

from __future__ import annotations

import os
from typing import Iterator, List

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def build_storage_path(*segments: str) -> str:
    """Join *segments* into a normalized POSIX-style storage path.

    ``MEDIA_STORAGE_PREFIX`` (if defined) is automatically prepended so the
    returned value always points to the correct root within the configured
    storage backend.
    """

    components: List[str] = []
    base_prefix = getattr(settings, "MEDIA_STORAGE_PREFIX", "")
    for candidate in (base_prefix, *segments):
        if not candidate:
            continue
        normalized = str(candidate).strip("/")
        if normalized:
            components.append(normalized)
    return "/".join(components)


def storage_exists(path: str) -> bool:
    """Return ``True`` if *path* exists in the configured storage."""

    if os.path.isabs(path):
        return os.path.exists(path)
    return default_storage.exists(path)


def storage_delete(path: str) -> None:
    """Delete *path* from the storage backend (ignore missing files)."""

    if os.path.isabs(path):
        try:
            os.remove(path)
        except FileNotFoundError:
            return
    else:
        default_storage.delete(path)


def storage_read_bytes(path: str) -> bytes:
    """Read a file from storage returning its raw bytes."""

    if os.path.isabs(path):
        with open(path, 'rb') as fh:
            return fh.read()
    with default_storage.open(path, 'rb') as fh:
        return fh.read()


def storage_read_text(path: str, encoding: str = 'utf-8') -> str:
    """Read a text file from storage using *encoding*."""

    if os.path.isabs(path):
        with open(path, 'r', encoding=encoding) as fh:
            return fh.read()
    with default_storage.open(path, 'r') as fh:
        return fh.read()


def storage_write_bytes(path: str, data: bytes) -> str:
    """Persist *data* (bytes) into storage and return the stored name."""

    if os.path.isabs(path):
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(data)
        return path

    if default_storage.exists(path):
        default_storage.delete(path)
    return default_storage.save(path, ContentFile(data))


def storage_write_text(path: str, data: str, encoding: str = 'utf-8') -> str:
    """Persist *data* (text) into storage and return the stored name."""

    return storage_write_bytes(path, data.encode(encoding))


def iter_storage_files(prefix: str) -> Iterator[str]:
    """Yield all file paths recursively under *prefix* within the storage."""

    if os.path.isabs(prefix):
        for root, _, files in os.walk(prefix):
            for filename in files:
                yield os.path.join(root, filename)
        return

    stack: List[str] = [prefix.strip('/')]
    if not stack[0]:
        stack = ['']

    while stack:
        current = stack.pop()
        dirs, files = default_storage.listdir(current)
        base = current.strip('/')

        for filename in files:
            if base:
                yield f"{base}/{filename}"
            else:
                yield filename

        for directory in dirs:
            next_path = f"{base}/{directory}" if base else directory
            stack.append(next_path)
