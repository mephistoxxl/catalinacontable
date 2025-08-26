#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Servicio

# Test directo del servicio S000000002
print("🔍 DEBUGGING SERVICIO S000000002")
print("="*50)

servicio = Servicio.objects.filter(codigo__iexact='S000000002').first()
if servicio:
    print(f"✅ Servicio encontrado: {servicio.codigo}")
    print(f"📄 Descripción: {servicio.descripcion}")
    print(f"💰 Precio: {servicio.precio1}")
    print(f"📊 IVA field: {repr(servicio.iva)}")
    print(f"📊 IVA type: {type(servicio.iva)}")
    
    # Mapeo igual que en views.py
    MAPEO_IVA = {
        '0': 0.00,  # Sin IVA
        '5': 0.05,  # 5%
        '2': 0.12,  # 12%
        '10': 0.13, # 13%
        '3': 0.14,  # 14%
        '4': 0.15,  # 15%
        '9': 0.16,  # 16% - Agregado para servicios
        '6': 0.00,  # Exento
        '7': 0.00,  # Exento
        '8': 0.08   # 8%
    }
    
    iva_code = str(servicio.iva) if servicio.iva else '2'
    iva_percent = MAPEO_IVA.get(iva_code, 0.12)
    precio_base = float(servicio.precio1) if servicio.precio1 else 0.0
    precio_con_iva = precio_base * (1 + iva_percent)
    
    print(f"🔢 IVA code procesado: '{iva_code}'")
    print(f"📈 IVA porcentaje: {iva_percent}")
    print(f"💲 Precio base: {precio_base}")
    print(f"💲 Precio con IVA: {precio_con_iva}")
    print(f"📊 Diferencia esperada: 0.58 - 0.56 = {0.58 - 0.56}")
    
    # Verificar si coincide con el problema reportado
    if abs(precio_con_iva - 0.58) < 0.01:
        print("✅ ESTE SERVICIO GENERA $0.58 (coincide con Django)")
    elif abs(precio_con_iva - 0.56) < 0.01:
        print("❌ ESTE SERVICIO GENERA $0.56 (coincide con JavaScript)")
    
else:
    print("❌ Servicio S000000002 NO encontrado")

print("\n🔍 LISTANDO TODOS LOS SERVICIOS:")
print("="*50)
servicios = Servicio.objects.all()[:10]  # Primeros 10
for s in servicios:
    print(f"Código: {s.codigo}, IVA: {repr(s.iva)}, Precio: {s.precio1}")
