"""
Management command para eliminar facturas de un RUC específico
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from inventario.models import Empresa, Factura


class Command(BaseCommand):
    help = 'Elimina todas las facturas de un RUC específico'

    def add_arguments(self, parser):
        parser.add_argument('ruc', type=str, help='RUC de la empresa')
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirmar eliminación sin preguntar'
        )

    def handle(self, *args, **options):
        ruc = options['ruc']
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"ELIMINACIÓN DE FACTURAS - RUC: {ruc}")
        self.stdout.write(f"{'='*60}\n")
        
        # Buscar empresa
        empresa = Empresa.objects.filter(ruc=ruc).first()
        
        if not empresa:
            self.stdout.write(self.style.ERROR(f"❌ No se encontró empresa con RUC {ruc}"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"✅ Empresa: {empresa.razon_social}"))
        self.stdout.write(f"   RUC: {empresa.ruc}")
        self.stdout.write(f"   ID: {empresa.id}\n")
        
        # Contar facturas
        facturas = Factura._unsafe_objects.filter(empresa=empresa)
        total_facturas = facturas.count()
        
        if total_facturas == 0:
            self.stdout.write(self.style.WARNING("ℹ️  No hay facturas para eliminar"))
            return
        
        self.stdout.write(f"📊 Facturas a eliminar: {total_facturas}\n")
        
        # Confirmar si no se pasó el flag
        if not options['confirmar']:
            confirmar = input("¿Confirmar eliminación? (escriba 'SI'): ")
            if confirmar.strip().upper() != 'SI':
                self.stdout.write(self.style.WARNING("❌ Operación cancelada"))
                return
        
        # Eliminar
        self.stdout.write("🔄 Eliminando...")
        
        with transaction.atomic():
            deleted, details = facturas.delete()
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ ELIMINACIÓN COMPLETADA\n"))
            self.stdout.write("📋 Registros eliminados:")
            for modelo, cantidad in details.items():
                self.stdout.write(f"   • {modelo}: {cantidad}")
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ Total: {deleted} registros eliminados\n"))
