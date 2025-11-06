#!/usr/bin/env python3
"""CI helper que garantiza que no se suban certificados sensibles al repositorio."""

from __future__ import annotations

import pathlib
import subprocess
import sys
from typing import Iterable

PROTECTED_EXTENSIONS = {".p12", ".pfx", ".p7m", ".pem", ".cer", ".crt", ".key"}
PROTECTED_PATTERNS = ("firmas_secure/firmas/",)


def iter_tracked_files() -> Iterable[pathlib.Path]:
    """Devuelve todos los archivos versionados en Git."""

    result = subprocess.run(
        ["git", "ls-files"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr or "Error ejecutando git ls-files\n")
        sys.exit(result.returncode or 1)
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            yield pathlib.Path(line)


def is_protected(path: pathlib.Path) -> bool:
    normalized = str(path).replace("\\", "/")
    if any(pattern in normalized for pattern in PROTECTED_PATTERNS):
        return True
    return path.suffix.lower() in PROTECTED_EXTENSIONS


def main() -> int:
    offending = [str(path) for path in iter_tracked_files() if is_protected(path)]
    if offending:
        sys.stderr.write(
            "Se detectaron archivos de certificados versionados, lo cual no está permitido:\n"
        )
        for path in offending:
            sys.stderr.write(f"  - {path}\n")
        sys.stderr.write(
            "Elimina los archivos y utiliza almacenamiento seguro (S3) antes de continuar.\n"
        )
        return 1
    print("✅ Sin certificados sensibles versionados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
