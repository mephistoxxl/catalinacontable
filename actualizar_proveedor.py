#!/usr/bin/env python
"""
Script para crear migración y actualizar el modelo Proveedor con nuevos campos
"""
import os
import django
import sys

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from django.core.management import call_command

def main():
    print("🔧 Creando migración para actualizar el modelo Proveedor...")
    try:
        # Crear migración
        call_command('makemigrations', 'inventario', name='actualizar_proveedor_campos', verbosity=2)
        print("✅ Migración creada exitosamente")
        
        print("\n🚀 Aplicando migración...")
        # Aplicar migración
        call_command('migrate', 'inventario', verbosity=2)
        print("✅ Migración aplicada exitosamente")
        
        print("\n📊 Mostrando estado actual de migraciones...")
        call_command('showmigrations', 'inventario')
        
        print("\n✅ PROCESO COMPLETADO EXITOSAMENTE")
        print("🎉 El modelo Proveedor ahora tiene los mismos campos que Cliente")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
