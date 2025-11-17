"""
Script para ver todas las facturas y sus estados
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura

print("\n" + "="*80)
print("🔍 TODAS LAS FACTURAS EN EL SISTEMA")
print("="*80 + "\n")

facturas = Factura.objects.all().order_by('-id')[:10]

if not facturas.exists():
    print("❌ No hay facturas en el sistema")
else:
    print(f"✅ Mostrando últimas {facturas.count()} facturas\n")
    
    for factura in facturas:
        print(f"\n📄 Factura #{factura.id} - Secuencia: {factura.secuencia}")
        print(f"   Estado interno: {getattr(factura, 'estado', 'N/A')}")
        print(f"   Estado SRI: {getattr(factura, 'estado_sri', 'N/A')}")
        print(f"   📅 Fecha Emisión:      {factura.fecha_emision}")
        print(f"   📅 Fecha Autorización: {getattr(factura, 'fecha_autorizacion', 'N/A')}")
        print(f"   🔢 Número Autorización: {getattr(factura, 'numero_autorizacion', 'N/A')}")
        print(f"   🔑 Clave Acceso: {factura.clave_acceso[:20]}..." if factura.clave_acceso else "   🔑 Sin clave")
        print(f"   " + "-"*70)

print("\n" + "="*80 + "\n")
