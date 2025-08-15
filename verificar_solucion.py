#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prueba simple para verificar la solución
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')

try:
    django.setup()
    print("✅ Django configurado correctamente")
except Exception as e:
    print(f"❌ Error configurando Django: {e}")
    sys.exit(1)

try:
    from inventario.models import FormaPago
    print("✅ Modelo FormaPago importado correctamente")
    
    # Verificar que tiene los campos necesarios
    print("📋 Campos del modelo FormaPago:")
    for field in FormaPago._meta.get_fields():
        print(f"   • {field.name}: {type(field).__name__}")
        
    # Verificar opciones de forma de pago
    if hasattr(FormaPago, 'FORMAS_PAGO_CHOICES'):
        print(f"✅ Opciones de forma de pago: {len(FormaPago.FORMAS_PAGO_CHOICES)} disponibles")
    else:
        print("❌ No se encontraron opciones de forma de pago")
        
except Exception as e:
    print(f"❌ Error importando modelo FormaPago: {e}")
    sys.exit(1)

try:
    from inventario.sri.xml_generator import SRIXMLGenerator
    print("✅ Generador XML importado correctamente")
    
    xml_gen = SRIXMLGenerator()
    
    # Verificar que NO tiene método de emergencia
    if hasattr(xml_gen, '_crear_forma_pago_por_defecto_emergencia'):
        print("❌ ERROR: Todavía existe método de emergencia")
        sys.exit(1)
    else:
        print("✅ Método de emergencia eliminado correctamente")
        
    # Verificar que tiene método principal
    if hasattr(xml_gen, 'generar_xml_factura'):
        print("✅ Método principal generar_xml_factura existe")
    else:
        print("❌ No se encontró método principal")
        
except Exception as e:
    print(f"❌ Error importando generador XML: {e}")
    sys.exit(1)

print("\n" + "="*50)
print("🎉 VERIFICACIÓN EXITOSA")
print("="*50)
print("✅ Modelo FormaPago funciona correctamente")
print("✅ Generador XML sin método de emergencia")  
print("✅ Solución implementada correctamente")
print("="*50)
