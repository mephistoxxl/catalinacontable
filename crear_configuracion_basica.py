#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Empresa, Opciones

def crear_configuracion_basica():
    print("=== CREANDO CONFIGURACIÓN BÁSICA ===")
    
    # Obtener empresa
    empresa = Empresa.objects.first()
    if not empresa:
        print("❌ No hay empresa en PostgreSQL")
        return
    
    print(f"🏢 Empresa: {empresa.razon_social} ({empresa.ruc})")
    
    # Eliminar configuración existente si existe
    Opciones.objects.filter(empresa=empresa).delete()
    
    # Crear configuración básica válida
    try:
        config = Opciones.objects.create(
            empresa=empresa,
            identificacion=empresa.ruc,
            razon_social=empresa.razon_social,
            nombre_comercial=empresa.razon_social,
            direccion_establecimiento='Av. Principal 123, Ciudad, País',
            telefono='0999999999',
            correo='admin@empresa.com',
            obligado='NO',
            tipo_regimen='GENERAL'
        )
        
        print(f"✅ Configuración creada exitosamente")
        print(f"   RUC: {config.identificacion}")
        print(f"   Razón Social: {config.razon_social}")
        print(f"   Dirección: {config.direccion_establecimiento}")
        print(f"   Email: {config.correo}")
        print(f"   Teléfono: {config.telefono}")
        
    except Exception as e:
        print(f"❌ Error creando configuración: {e}")

if __name__ == '__main__':
    crear_configuracion_basica()
