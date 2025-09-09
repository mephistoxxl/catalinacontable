#!/usr/bin/env python
"""
Limpieza segura del repo: lista (y opcionalmente mueve o elimina) archivos de pruebas/soporte
que no son necesarios para producción.

Uso:
  python scripts/cleanup.py --dry-run         # Solo listar candidatos con tamaños
  python scripts/cleanup.py --apply           # Mover candidatos a scripts/archive/
  python scripts/cleanup.py --delete          # ELIMINAR definitivamente (¡peligroso!)

Siempre revisa la salida antes de aplicar.
"""
import argparse
import fnmatch
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "scripts" / "archive"


FILE_PATTERNS = [
    # Scripts de depuración/migración/soporte
    "debug_*.py",
    "verificar_*.py",
    "migrar_*.py",
    "migrate_to_postgresql.py",
    "full_migration.py",
    "cargar_*.py",
    "backup_sqlite.py",
    "load_data_manual.py",
    "restaurar_empresa_original.py",
    "check_*.py",
    "fix_*.py",
    "eliminar_*.py",
    "temp_fix.py",
    "ejemplo_sri.py",
    "pdf_signing_standalone.py",
    "install_postgresql.ps1",
    # Logs y artefactos
    "*.log",
    "2.17.0",
    "BDD.sqlite3",
    "db.sqlite3",
]

# Directorios candidatos completos
DIR_CANDIDATES = [
    "node_modules",
    # Contenido generado
    "staticfiles",
    # Cuidado: media puede contener datos de firma. Se lista pero no se actúa sin --delete.
    "media",
]

# Tests (opcionales): mantener por defecto, solo archivar con --apply-tests
TEST_PATTERNS = [
    "test_*.py",
]
TEST_DIRS = [
    str(Path("inventario") / "tests"),
]


KEEP_FILES = {
    "manage.py",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "README.md",
    "Procfile",
}

KEEP_DIR_PREFIXES = (
    "inventario",
    "sistema",
    ".git",
    ".vscode",
    ".idea",
    "venv",
    "scripts/cleanup.py",
)


def human_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def should_keep(path: Path) -> bool:
    rel = str(path.relative_to(ROOT))
    if path.name in KEEP_FILES:
        return True
    for prefix in KEEP_DIR_PREFIXES:
        if rel == prefix or rel.startswith(prefix + "/"):
            return True
    return False


def collect_candidates(include_tests: bool):
    files = []
    dirs = []

    # File patterns
    for root, _, filenames in os.walk(ROOT):
        root_path = Path(root)
        for name in filenames:
            p = root_path / name
            rel = p.relative_to(ROOT)
            if should_keep(p):
                continue
            # tests
            matched = any(fnmatch.fnmatch(name, pat) for pat in FILE_PATTERNS)
            if include_tests:
                matched = matched or any(fnmatch.fnmatch(name, pat) for pat in TEST_PATTERNS)
            # limitar a raíz (no borrar dentro de inventario/sistema por patrones generales)
            if matched and rel.parts and rel.parts[0] not in ("inventario", "sistema"):
                files.append(p)

    # Dir candidates (solo si existen)
    for d in DIR_CANDIDATES:
        dp = ROOT / d
        if dp.exists() and not should_keep(dp):
            dirs.append(dp)

    if include_tests:
        for td in TEST_DIRS:
            dp = ROOT / td
            if dp.exists():
                dirs.append(dp)

    return files, dirs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Solo listar candidatos")
    ap.add_argument("--apply", action="store_true", help="Mover a scripts/archive/")
    ap.add_argument("--delete", action="store_true", help="Eliminar definitivamente")
    ap.add_argument("--apply-tests", action="store_true", help="Incluir tests como candidatos")
    args = ap.parse_args()

    files, dirs = collect_candidates(include_tests=args.apply_tests)

    print("=== Candidatos (archivos) ===")
    total_size = 0
    for f in files:
        try:
            size = f.stat().st_size
        except OSError:
            size = 0
        total_size += size
        print(f"- {f.relative_to(ROOT)} \t {human_size(size)}")
    print(f"Total archivos: {len(files)} | Tamaño: {human_size(total_size)}")

    print("\n=== Candidatos (directorios) ===")
    for d in dirs:
        print(f"- {d.relative_to(ROOT)}/")

    if args.dry_run or (not args.apply and not args.delete):
        print("\nDry-run: no se realizaron cambios. Usa --apply para mover o --delete para eliminar.")
        return

    if args.apply:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for f in files:
            dst = ARCHIVE_DIR / f.name
            try:
                shutil.move(str(f), str(dst))
                print(f"Archivado: {f.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
            except Exception as e:
                print(f"! No se pudo archivar {f}: {e}")
        for d in dirs:
            dst = ARCHIVE_DIR / d.name
            try:
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(d), str(dst))
                print(f"Archivado dir: {d.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
            except Exception as e:
                print(f"! No se pudo archivar dir {d}: {e}")
        return

    if args.delete:
        for f in files:
            try:
                f.unlink()
                print(f"Eliminado: {f.relative_to(ROOT)}")
            except Exception as e:
                print(f"! No se pudo eliminar {f}: {e}")
        for d in dirs:
            try:
                shutil.rmtree(d)
                print(f"Eliminado dir: {d.relative_to(ROOT)}")
            except Exception as e:
                print(f"! No se pudo eliminar dir {d}: {e}")


if __name__ == "__main__":
    main()
