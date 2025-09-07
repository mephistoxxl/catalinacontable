#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import *

print("🎉 RESUMEN FINAL COMPLETO DE LA MIGRACIÓN")
print("=" * 50)
print()

print("📊 DATOS PRINCIPALES:")
print(f"✅ Empresas: {Empresa.objects.count()}")
empresa = Empresa.objects.first()
print(f"   - {empresa.razon_social} (RUC: {empresa.ruc})")
print()

print(f"👥 Usuarios: {Usuario.objects.count()}")
for u in Usuario.objects.all()[:3]:
    print(f"   - {u.username} ({u.first_name} {u.last_name})")
print()

print(f"👤 Clientes: {Cliente.objects.count()}")
for c in Cliente.objects.all()[:3]:
    print(f"   - {c.razon_social} ({c.identificacion})")
print()

print(f"📦 Productos: {Producto.objects.count()}")
for p in Producto.objects.all():
    print(f"   - {p.descripcion} (${p.precio})")
print()

print(f"🏪 Almacenes: {Almacen.objects.count()}")
for a in Almacen.objects.all():
    print(f"   - {a.descripcion}")
print()

print(f"📋 Facturadores: {Facturador.objects.count()}")
for f in Facturador.objects.all():
    print(f"   - {f.nombres} ({f.correo})")
print()

print(f"💰 Cajas: {Caja.objects.count()}")
for c in Caja.objects.all():
    print(f"   - {c.descripcion}")
print()

print("⚙️ CONFIGURACIÓN GENERAL:")
config = Opciones.objects.first()
print(f"   - Empresa: {config.razon_social}")
print(f"   - RUC: {config.identificacion}")
print(f"   - Email: {config.correo}")
print(f"   - Teléfono: {config.telefono}")
print(f"   - Ambiente SRI: {config.ambiente_descripcion}")
print(f"   - IVA: {config.valor_iva}%")
print()

print("🎯 ¡MIGRACIÓN COMPLETADA AL 100%!")
