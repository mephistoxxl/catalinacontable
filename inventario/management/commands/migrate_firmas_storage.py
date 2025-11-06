from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand, CommandError

from inventario.models import Opciones
from inventario.storage import EncryptedFirmaStorage


class Command(BaseCommand):
    help = (
        "Migra las firmas electrónicas locales al backend configurado en ``EncryptedFirmaStorage`` "
        "(por ejemplo, S3) aplicando cifrado activo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--source-dir',
            help=(
                'Directorio raíz donde residen actualmente las firmas sin cifrar. '
                'Por defecto se usa FIRMAS_ROOT o <BASE_DIR>/firmas_secure.'
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué archivos se migrarían sin realizar cambios.',
        )
        parser.add_argument(
            '--skip-validation',
            action='store_true',
            help='Omite la verificación de cifrado y backend remoto (no recomendado).',
        )
        parser.add_argument(
            '--delete-source',
            action='store_true',
            help='Elimina el archivo de origen una vez migrado exitosamente.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Límite opcional de registros a procesar (para migraciones progresivas).',
        )

    def handle(self, *args, **options):
        storage = EncryptedFirmaStorage()
        if not options.get('skip_validation'):
            errors = storage.validate_configuration()
            if errors:
                formatted = '\n'.join(f"  - {error}" for error in errors)
                raise CommandError(
                    'Configuración de almacenamiento de firmas insegura:\n' f'{formatted}'
                )

        default_source = getattr(settings, 'FIRMAS_ROOT', None) or os.path.join(
            settings.BASE_DIR, 'firmas_secure'
        )
        source_dir = Path(options.get('source_dir') or default_source).expanduser()
        legacy_storage = FileSystemStorage(location=str(source_dir))
        if not source_dir.exists():
            raise CommandError(f'El directorio de origen {source_dir} no existe.')

        qs = (
            Opciones.all_objects.exclude(firma_electronica__isnull=True)
            .exclude(firma_electronica='')
            .order_by('id')
        )
        limit = options.get('limit')
        if limit:
            qs = qs[:limit]

        processed = 0
        migrated = 0
        missing = []

        for opcion in qs:
            processed += 1
            name = opcion.firma_electronica.name
            if not name:
                continue

            if not legacy_storage.exists(name):
                missing.append(name)
                self.stdout.write(
                    self.style.WARNING(
                        f"[OMITIDO] {name} no se encontró en {source_dir}; verifique el respaldo."
                    )
                )
                continue

            if options.get('dry_run'):
                self.stdout.write(f"[DRY-RUN] migraría {name}")
                migrated += 1
                continue

            with legacy_storage.open(name, 'rb') as source_file:
                payload = source_file.read()

            storage.save(name, ContentFile(payload))
            migrated += 1
            self.stdout.write(self.style.SUCCESS(f"[OK] {name} migrado a almacenamiento seguro"))

            if options.get('delete_source'):
                legacy_storage.delete(name)

        self.stdout.write('--- Resumen ---')
        self.stdout.write(f'Total procesado: {processed}')
        self.stdout.write(f'Migrados: {migrated}')
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f'Archivos no encontrados: {len(missing)}. Revise el respaldo antes de eliminarlos.'
                )
            )
        else:
            self.stdout.write('Sin archivos faltantes detectados.')

        if migrated == 0 and not missing and not options.get('dry_run'):
            self.stdout.write('No hubo archivos que migrar. Verifique que existan firmas activas.')
