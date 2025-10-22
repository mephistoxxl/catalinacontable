from django.core.management.base import BaseCommand
from django.db import transaction
from inventario.models import Empresa, Usuario
from inventario.guia_remision.models_secuencia import SecuenciaGuia


class Command(BaseCommand):
    help = 'Crear secuencias iniciales de guías de remisión para todas las empresas activas'

    def handle(self, *args, **options):
        with transaction.atomic():
            empresas = Empresa.objects.all()
            usuario_root = Usuario.objects.filter(is_superuser=True).first()
            
            if not usuario_root:
                self.stdout.write(self.style.ERROR('No se encontró usuario ROOT'))
                return
            
            created_count = 0
            skipped_count = 0
            
            for empresa in empresas:
                existe = SecuenciaGuia.objects.filter(empresa=empresa).exists()
                
                if not existe:
                    secuencia = SecuenciaGuia.objects.create(
                        empresa=empresa,
                        descripcion='Secuencia Principal',
                        establecimiento='001',
                        punto_emision='001',
                        secuencial_actual=0,
                        activo=True,
                        usuario_creacion=usuario_root
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Secuencia creada para {empresa.razon_social}: {secuencia.numero_completo_actual}'
                        )
                    )
                    created_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'• Empresa {empresa.razon_social} ya tiene secuencias'
                        )
                    )
                    skipped_count += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Proceso completado: {created_count} creadas, {skipped_count} omitidas'
                )
            )
