#!/usr/bin/env python
"""Script para verificar archivos logo en S3"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from django.core.files.storage import default_storage

print("=" * 60)
print("VERIFICANDO ARCHIVOS EN S3")
print("=" * 60)

# Listar todos los archivos en el directorio de logos
try:
    dirs, files = default_storage.listdir('static/inventario/assets/logo')
    print(f"\n📁 Archivos en 'static/inventario/assets/logo':")
    for file in files:
        full_path = f'static/inventario/assets/logo/{file}'
        exists = default_storage.exists(full_path)
        size = default_storage.size(full_path) if exists else 0
        print(f"  {'✅' if exists else '❌'} {file} ({size} bytes)")
except Exception as e:
    print(f"❌ Error listando directorio: {e}")

# Verificar específicamente el logo-catalina.png
print(f"\n🔍 Verificando 'logo-catalina.png':")
logo_path = 'static/inventario/assets/logo/logo-catalina.png'
exists = default_storage.exists(logo_path)
print(f"  Existe: {'✅ SÍ' if exists else '❌ NO'}")

if exists:
    try:
        size = default_storage.size(logo_path)
        url = default_storage.url(logo_path)
        print(f"  Tamaño: {size} bytes")
        print(f"  URL: {url}")
    except Exception as e:
        print(f"  Error obteniendo info: {e}")

# Intentar abrir el archivo
print(f"\n📖 Intentando abrir el archivo:")
try:
    with default_storage.open(logo_path, 'rb') as f:
        data = f.read()
        print(f"  ✅ Archivo abierto exitosamente")
        print(f"  Tamaño leído: {len(data)} bytes")
        print(f"  Primeros 10 bytes: {data[:10]}")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n" + "=" * 60)
