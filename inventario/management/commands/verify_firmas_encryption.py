from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from inventario.storage import EncryptedFirmaStorage


class Command(BaseCommand):
    help = (
        'Verifica que la configuración de EncryptedFirmaStorage use almacenamiento remoto y cifrado activo '
        'antes de cargar nuevas firmas electrónicas.'
    )

    def handle(self, *args, **options):
        storage = EncryptedFirmaStorage()
        errors = storage.validate_configuration()
        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise CommandError(
                'La configuración de almacenamiento de firmas no es segura. Corrige los problemas antes de continuar.'
            )

        self.stdout.write(
            self.style.SUCCESS(
                'EncryptedFirmaStorage está listo: cifrado activo y almacenamiento remoto configurado.'
            )
        )
