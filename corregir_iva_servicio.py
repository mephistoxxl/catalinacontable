#!/usr/bin/env python3

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Servicio

print("🔍 BUSCANDO SERVICIOS CON PRECIO ~$0.5")
print("="*50)

# Buscar servicios con precio cerca de 0.5
servicios = Servicio.objects.filter(precio1__gte=0.45, precio1__lte=0.55)

for servicio in servicios:
    precio = float(servicio.precio1) if servicio.precio1 else 0.0
    
    # Calcular lo que daría con 12% y 16%
    precio_12 = precio * 1.12  # $0.56 si precio es $0.5
    precio_16 = precio * 1.16  # $0.58 si precio es $0.5
    
    print(f"📦 SERVICIO: {servicio.codigo}")
    print(f"   Descripción: {servicio.descripcion}")
    print(f"   Precio base: ${precio}")
    print(f"   IVA actual: {repr(servicio.iva)}")
    print(f"   Con 12% IVA: ${precio_12:.2f}")
    print(f"   Con 16% IVA: ${precio_16:.2f}")
    
    if abs(precio_12 - 0.56) < 0.01:
        print(f"   ⚠️ ESTE SERVICIO GENERA $0.56 CON 12% (CAUSA EL ERROR)")
        print(f"   💡 NECESITA CAMBIAR IVA DE '{servicio.iva}' A '9' PARA 16%")
        
        # Auto-corregir si es el servicio problemático
        if abs(precio - 0.5) < 0.01:  # Si el precio es exactamente $0.5
            print(f"   🔧 CORRIGIENDO IVA AUTOMÁTICAMENTE...")
            servicio.iva = '9'  # 16% IVA
            servicio.save()
            print(f"   ✅ IVA CAMBIADO A '9' (16%)")
    
    print("-" * 30)

print("\n🔍 VERIFICANDO SERVICIO S000000002 ESPECÍFICAMENTE")
print("="*50)

servicio = Servicio.objects.filter(codigo__iexact='S000000002').first()
if servicio:
    precio = float(servicio.precio1) if servicio.precio1 else 0.0
    print(f"✅ Encontrado: {servicio.codigo}")
    print(f"   Precio: ${precio}")
    print(f"   IVA: {repr(servicio.iva)}")
    
    if servicio.iva == '2':
        print(f"   ⚠️ IVA ES '2' (12%) - CAMBIANDO A '9' (16%)")
        servicio.iva = '9'
        servicio.save()
        print(f"   ✅ IVA CORREGIDO A '9' (16%)")
    else:
        print(f"   ✅ IVA YA ES '{servicio.iva}'")
else:
    print("❌ Servicio S000000002 no encontrado")
