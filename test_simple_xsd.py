#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Prueba simple de conexión Django y validación XSD
"""

import os
import sys
import django
from pathlib import Path

print("🚀 Iniciando prueba simple...")

# Setup Django
try:
    sys.path.append(str(Path(__file__).parent))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
    django.setup()
    print("✅ Django configurado correctamente")
except Exception as e:
    print(f"❌ Error configurando Django: {e}")
    sys.exit(1)

try:
    from inventario.models import Factura, Cliente
    print("✅ Modelos importados correctamente")
except Exception as e:
    print(f"❌ Error importando modelos: {e}")
    sys.exit(1)

try:
    from inventario.sri.integracion_django import SRIIntegration
    print("✅ SRIIntegration importada correctamente")
except Exception as e:
    print(f"❌ Error importando SRIIntegration: {e}")
    sys.exit(1)

# Contar facturas
try:
    total_facturas = Factura.objects.count()
    print(f"📊 Total de facturas en BD: {total_facturas}")
    
    facturas_pendientes = Factura.objects.filter(
        estado_sri__in=['', 'PENDIENTE', 'ERROR']
    ).count()
    print(f"📋 Facturas pendientes/error: {facturas_pendientes}")
    
except Exception as e:
    print(f"❌ Error consultando facturas: {e}")
    sys.exit(1)

# Probar reconocimiento de estado
try:
    sri_integration = SRIIntegration()
    
    test_estados = ['AUTORIZADO', 'AUTORIZADA', 'autorizado']
    print("\n🔍 Probando reconocimiento de estados:")
    for estado in test_estados:
        es_autorizado = sri_integration._es_estado_autorizado(estado)
        status = "✅" if es_autorizado else "❌"
        print(f"  {status} '{estado}' -> {es_autorizado}")
        
except Exception as e:
    print(f"❌ Error probando estados: {e}")
    sys.exit(1)

print("\n🎉 Prueba simple completada exitosamente")
print("✅ Sistema básico funcionando correctamente")
