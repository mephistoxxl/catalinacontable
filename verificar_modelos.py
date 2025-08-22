"""
Script simple para verificar los cambios en el modelo Proveedor
"""
import sys
import os

# Configurar el path
sys.path.append('c:\\Users\\CORE I7\\Desktop\\sisfact')

# Configurar Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'sistema.settings'

import django
try:
    django.setup()
    print("✅ Django configurado correctamente")
    
    # Importar modelo
    from inventario.models import Proveedor, Cliente
    
    # Verificar campos de Cliente
    print("\n📋 Campos del modelo Cliente:")
    for field in Cliente._meta.fields:
        print(f"  - {field.name}: {type(field).__name__}")
    
    # Verificar campos de Proveedor
    print("\n📋 Campos del modelo Proveedor:")
    for field in Proveedor._meta.fields:
        print(f"  - {field.name}: {type(field).__name__}")
    
    print("\n🔧 Es necesario crear una migración para sincronizar los modelos")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("Necesitamos crear la migración manualmente")
