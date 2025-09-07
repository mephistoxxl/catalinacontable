#!/usr/bin/env python
import os
import django
import json
from decimal import Decimal
from datetime import datetime
from django.utils import timezone

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import *

def parse_decimal(value):
    if value is None or value == '':
        return Decimal('0')
    return Decimal(str(value))

def migrar_datos_restantes():
    print("📦 MIGRACIÓN DE DATOS RESTANTES")
    print("===============================")
    
    # Cargar backup
    with open('backup_sqlite_data.json', 'r') as f:
        backup_data = json.load(f)
    
    # Obtener empresa existente
    empresa = Empresa.objects.first()
    if not empresa:
        print("❌ No hay empresa configurada")
        return
    
    print(f"✅ Empresa encontrada: {empresa.razon_social}")
    
    # Limpiar datos existentes que van a remigrarse
    print("\n🗑️ Limpiando datos existentes...")
    Producto.objects.all().delete()
    Almacen.objects.all().delete()
    Facturador.objects.all().delete()
    Caja.objects.all().delete()
    
    # 1. CARGAR PRODUCTOS
    print("\n📦 Cargando productos...")
    productos_data = [item for item in backup_data if item['model'] == 'inventario.producto']
    for item in productos_data:
        fields = item['fields']
        try:
            producto = Producto.objects.create(
                empresa=empresa,
                codigo=fields.get('codigo', ''),
                codigo_barras=fields.get('codigo_barras', ''),
                descripcion=fields.get('descripcion', ''),
                precio=parse_decimal(fields.get('precio', '0')),
                precio2=parse_decimal(fields.get('precio2')) if fields.get('precio2') else None,
                disponible=int(fields.get('disponible', 0)),
                categoria=fields.get('categoria', '1'),
                iva=fields.get('iva', '2'),
                costo_actual=parse_decimal(fields.get('costo_actual', '0')),
                precio_iva1=parse_decimal(fields.get('precio_iva1', '0')),
                precio_iva2=parse_decimal(fields.get('precio_iva2', '0'))
            )
            print(f"✅ Producto: {producto.descripcion} (${producto.precio})")
        except Exception as e:
            print(f"❌ Error en producto {fields.get('descripcion', '?')}: {e}")
    
    # 2. CARGAR ALMACENES
    print("\n🏪 Cargando almacenes...")
    almacenes_data = [item for item in backup_data if item['model'] == 'inventario.almacen']
    for item in almacenes_data:
        fields = item['fields']
        try:
            almacen = Almacen.objects.create(
                empresa=empresa,
                descripcion=fields.get('descripcion', fields.get('numero', 'Almacén Principal')),
                activo=True
            )
            print(f"✅ Almacén: {almacen.descripcion}")
        except Exception as e:
            print(f"❌ Error en almacén {fields.get('descripcion', '?')}: {e}")
    
    # 3. CARGAR FACTURADORES
    print("\n📋 Cargando facturadores...")
    facturadores_data = [item for item in backup_data if item['model'] == 'inventario.facturador']
    for item in facturadores_data:
        fields = item['fields']
        try:
            pk = item.get('pk', 1)
            facturador = Facturador.objects.create(
                empresa=empresa,
                nombres=fields.get('nombres', fields.get('nombre', f'Facturador {pk}')),
                telefono=fields.get('telefono', ''),
                correo=fields.get('correo', f"facturador{pk}@empresa.com"),
                activo=True,
                descuento_permitido=Decimal('0.00')
            )
            print(f"✅ Facturador: {facturador.nombres} - {facturador.correo}")
        except Exception as e:
            print(f"❌ Error en facturador {fields.get('nombres', fields.get('nombre', '?'))}: {e}")
    
    # 4. CARGAR CAJAS
    print("\n💰 Cargando cajas...")
    cajas_data = [item for item in backup_data if item['model'] == 'inventario.caja']
    for item in cajas_data:
        fields = item['fields']
        try:
            caja = Caja.objects.create(
                empresa=empresa,
                descripcion=fields.get('descripcion', fields.get('nombre', 'Caja Principal')),
                activo=True
            )
            print(f"✅ Caja: {caja.descripcion}")
        except Exception as e:
            print(f"❌ Error en caja {fields.get('descripcion', '?')}: {e}")
    
    print("\n🎉 ¡Migración de datos restantes completada!")
    
    # Resumen final
    print("\n=== RESUMEN FINAL ===")
    print(f"Empresas: {Empresa.objects.count()}")
    print(f"Usuarios: {Usuario.objects.count()}")
    print(f"Clientes: {Cliente.objects.count()}")
    print(f"Productos: {Producto.objects.count()}")
    print(f"Almacenes: {Almacen.objects.count()}")
    print(f"Facturadores: {Facturador.objects.count()}")
    print(f"Cajas: {Caja.objects.count()}")
    print(f"Configuraciones: {Opciones.objects.count()}")

if __name__ == "__main__":
    migrar_datos_restantes()
