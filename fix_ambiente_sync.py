#!/usr/bin/env python
"""
Sincroniza tipo_ambiente: copia de Opciones a Empresa
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Empresa, Opciones

print("\n=== SINCRONIZACIÓN DE AMBIENTE ===\n")

for empresa in Empresa.objects.all():
    print(f"Empresa: {empresa.razon_social} (RUC {empresa.ruc})")
    print(f"  Antes - Empresa.tipo_ambiente: {empresa.tipo_ambiente}")
    
    try:
        opciones = Opciones.objects.for_tenant(empresa).first()
        if opciones:
            print(f"  Opciones.tipo_ambiente: {opciones.tipo_ambiente}")
            
            if empresa.tipo_ambiente != opciones.tipo_ambiente:
                print(f"  ⚙️ Actualizando Empresa.tipo_ambiente: {empresa.tipo_ambiente} → {opciones.tipo_ambiente}")
                empresa.tipo_ambiente = opciones.tipo_ambiente
                empresa.save()
                print(f"  ✅ Sincronizado")
            else:
                print(f"  ✅ Ya estaban sincronizados")
        else:
            print(f"  ⚠️ NO HAY OPCIONES - manteniendo Empresa.tipo_ambiente={empresa.tipo_ambiente}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print()

print("\n=== FIN ===\n")
