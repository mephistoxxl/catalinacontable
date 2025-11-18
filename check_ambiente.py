#!/usr/bin/env python
"""
Script para verificar configuración de ambiente en producción
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Empresa, Opciones

print("\n=== VERIFICACIÓN DE AMBIENTE ===\n")

for empresa in Empresa.objects.all():
    print(f"Empresa: {empresa.razon_social}")
    print(f"  RUC: {empresa.ruc}")
    print(f"  tipo_ambiente: {empresa.tipo_ambiente}")
    
    try:
        opciones = Opciones.objects.for_tenant(empresa).first()
        if opciones:
            print(f"  Opciones.tipo_ambiente: {opciones.tipo_ambiente}")
            if empresa.tipo_ambiente != opciones.tipo_ambiente:
                print(f"  ⚠️ DESINCRONIZADO! Empresa={empresa.tipo_ambiente}, Opciones={opciones.tipo_ambiente}")
        else:
            print(f"  ⚠️ NO HAY OPCIONES")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print()

print("\n=== FIN ===\n")
