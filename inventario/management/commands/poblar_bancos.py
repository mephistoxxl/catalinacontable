from django.core.management.base import BaseCommand
from inventario.models import Banco

class Command(BaseCommand):
    help = 'Pobla la base de datos con bancos iniciales del Ecuador'

    def handle(self, *args, **options):
        bancos_ecuador = [
            {'banco': 'Banco Pichincha', 'secuencial_cheque': 1},
            {'banco': 'Banco del Pacífico', 'secuencial_cheque': 1},
            {'banco': 'Banco de Guayaquil', 'secuencial_cheque': 1},
            {'banco': 'Banco Internacional', 'secuencial_cheque': 1},
            {'banco': 'Banco Bolivariano', 'secuencial_cheque': 1},
            {'banco': 'Banco Produbanco', 'secuencial_cheque': 1},
            {'banco': 'Banco del Austro', 'secuencial_cheque': 1},
            {'banco': 'Banco Solidario', 'secuencial_cheque': 1},
            {'banco': 'Banco ProCredit', 'secuencial_cheque': 1},
            {'banco': 'Banco Machala', 'secuencial_cheque': 1},
            {'banco': 'Banco Coopnacional', 'secuencial_cheque': 1},
            {'banco': 'Banco Capital', 'secuencial_cheque': 1},
            {'banco': 'Banco Finca', 'secuencial_cheque': 1},
            {'banco': 'Banco D-Miro', 'secuencial_cheque': 1},
            {'banco': 'Banco Amazonas', 'secuencial_cheque': 1},
        ]

        creados = 0
        existentes = 0

        for banco_data in bancos_ecuador:
            banco, created = Banco.objects.get_or_create(
                banco=banco_data['banco'],
                defaults={
                    'titular': 'No especificado',
                    'numero_cuenta': '0000000000',
                    'tipo_cuenta': 'ahorros',
                    'fecha_apertura': None,
                    'telefono': '',
                    'secuencial_cheque': banco_data['secuencial_cheque'],
                    'activo': True
                }
            )
            
            if created:
                creados += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Banco creado: {banco.banco}')
                )
            else:
                existentes += 1
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Banco ya existe: {banco.banco}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Resumen:\n'
                f'   • Bancos creados: {creados}\n'
                f'   • Bancos existentes: {existentes}\n'
                f'   • Total en base de datos: {Banco.objects.count()}'
            )
        )
