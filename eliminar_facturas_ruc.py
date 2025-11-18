"""
Script seguro para eliminar facturas de un RUC específico en Heroku
Uso: heroku run python eliminar_facturas_ruc.py --app catalinasoft-ec
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Empresa, Factura, DetalleFactura
from django.db import transaction

RUC_OBJETIVO = '1713959011001'

def eliminar_facturas_ruc():
    """Elimina todas las facturas asociadas al RUC especificado"""
    
    print(f"\n{'='*60}")
    print(f"ELIMINACIÓN DE FACTURAS - RUC: {RUC_OBJETIVO}")
    print(f"{'='*60}\n")
    
    try:
        # Buscar la empresa
        empresa = Empresa.objects.filter(ruc=RUC_OBJETIVO).first()
        
        if not empresa:
            print(f"❌ No se encontró empresa con RUC {RUC_OBJETIVO}")
            return
        
        print(f"✅ Empresa encontrada: {empresa.razon_social}")
        print(f"   RUC: {empresa.ruc}")
        print(f"   ID: {empresa.id}\n")
        
        # Contar facturas antes de eliminar
        facturas = Factura._unsafe_objects.filter(empresa=empresa)
        total_facturas = facturas.count()
        
        if total_facturas == 0:
            print("ℹ️  No hay facturas para eliminar")
            return
        
        # Contar registros relacionados
        total_detalles = DetalleFactura._unsafe_objects.filter(factura__empresa=empresa).count()
        
        print(f"📊 RESUMEN DE REGISTROS A ELIMINAR:")
        print(f"   • Facturas: {total_facturas}")
        print(f"   • Detalles de factura: {total_detalles}")
        print(f"\n⚠️  Los siguientes registros también se eliminarán automáticamente (CASCADE):")
        print(f"   • FormaPago")
        print(f"   • CampoAdicional")
        print(f"   • TotalImpuesto")
        print(f"   • ImpuestoDetalle")
        print(f"   • NegociacionFactura")
        
        # Confirmación
        print(f"\n{'='*60}")
        confirmacion = input(f"¿CONFIRMAR ELIMINACIÓN de {total_facturas} facturas? (escriba 'ELIMINAR' para confirmar): ")
        
        if confirmacion.strip() != 'ELIMINAR':
            print("\n❌ Operación cancelada por el usuario")
            return
        
        # Ejecutar eliminación en transacción
        print(f"\n🔄 Iniciando eliminación...")
        
        with transaction.atomic():
            # Eliminar facturas (CASCADE eliminará automáticamente los registros relacionados)
            facturas_eliminadas, detalles = facturas.delete()
            
            print(f"\n✅ ELIMINACIÓN COMPLETADA")
            print(f"\n📋 Registros eliminados:")
            for modelo, cantidad in detalles.items():
                print(f"   • {modelo}: {cantidad}")
            
            print(f"\n✅ Total de registros eliminados: {facturas_eliminadas}")
        
        print(f"\n{'='*60}")
        print(f"✅ Proceso completado exitosamente")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    eliminar_facturas_ruc()
