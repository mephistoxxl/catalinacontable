"""
Script simple para verificar si fecha_autorizacion está guardada en BD
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura

print("\n" + "="*80)
print("🔍 VERIFICACIÓN DE FECHA DE AUTORIZACIÓN EN BASE DE DATOS")
print("="*80 + "\n")

# Buscar facturas autorizadas
facturas = Factura.objects.filter(estado_sri__in=['AUTORIZADA', 'AUTORIZADO']).order_by('-id')[:5]

if not facturas.exists():
    print("❌ No hay facturas autorizadas en el sistema")
else:
    print(f"✅ Encontradas {facturas.count()} facturas autorizadas\n")
    
    for factura in facturas:
        print(f"\n📄 Factura #{factura.id} - Secuencia: {factura.secuencia}")
        print(f"   Estado SRI: {factura.estado_sri}")
        print(f"   📅 Fecha Emisión:      {factura.fecha_emision}")
        print(f"   📅 Fecha Autorización: {factura.fecha_autorizacion}")
        print(f"   🔢 Número Autorización: {factura.numero_autorizacion}")
        
        # Verificar el problema
        if factura.fecha_autorizacion is None:
            print(f"   ⚠️  PROBLEMA: fecha_autorizacion es NULL en BD")
        elif factura.fecha_autorizacion == factura.fecha_emision:
            print(f"   ⚠️  PROBLEMA: fecha_autorizacion es igual a fecha_emision (error)")
        else:
            print(f"   ✅ fecha_autorizacion está correcta (diferente de emisión)")
        
        print(f"   " + "-"*70)

print("\n" + "="*80 + "\n")
