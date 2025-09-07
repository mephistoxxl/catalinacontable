#!/usr/bin/env python
import os
import django
import json
from decimal import Decimal
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from django.contrib.contenttypes.models import ContentType
from inventario.models import *

def cargar_todos_los_datos():
    print("=== CARGANDO TODOS LOS DATOS DEL BACKUP ===")
    
    # Leer el backup
    with open('backup_sqlite_data.json', 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    print(f"✅ Backup cargado: {len(backup_data)} registros encontrados")
    
    # Obtener empresa actual
    empresa = Empresa.objects.first()
    if not empresa:
        print("❌ No hay empresa en PostgreSQL")
        return
    
    print(f"🏢 Empresa actual: {empresa.razon_social} ({empresa.ruc})")
    
    # Cargar Opciones (Configuración)
    print("\n=== CARGANDO OPCIONES (CONFIGURACIÓN) ===")
    opciones_data = [item for item in backup_data if item['model'] == 'inventario.opciones']
    
    for item in opciones_data:
        fields = item['fields']
        try:
            opcion, created = Opciones.objects.get_or_create(
                empresa=empresa,
                defaults={
                    'identificacion': fields.get('identificacion', empresa.ruc),
                    'razon_social': fields.get('razon_social', empresa.razon_social),
                    'nombre_comercial': fields.get('nombre_comercial', ''),
                    'direccion_establecimiento': fields.get('direccion', '[CONFIGURAR DIRECCIÓN]'),
                    'telefono': fields.get('telefono', '0000000000'),
                    'correo': fields.get('correo', 'configurar@empresa.com'),
                    'obligado': 'SI' if fields.get('obligado', '1') == '1' else 'NO',
                    'tipo_regimen': 'GENERAL' if fields.get('tipo_regimen', '1') == '1' else 'RIMPE',
                    'password_firma': fields.get('password_firma', ''),
                    'fecha_caducidad_firma': fields.get('fecha_caducidad_firma', None)
                }
            )
            
            if created:
                print(f"✅ Configuración creada para {empresa.razon_social}")
            else:
                print(f"ℹ️ Configuración ya existe para {empresa.razon_social}")
                
        except Exception as e:
            print(f"❌ Error creando opciones: {e}")
    
    # Si no hay opciones en el backup, crear configuración básica
    if not opciones_data:
        print("ℹ️ No hay opciones en backup, creando configuración básica...")
        try:
            opcion = Opciones.objects.create(
                empresa=empresa,
                identificacion=empresa.ruc,
                razon_social=empresa.razon_social,
                nombre_comercial=empresa.razon_social,
                direccion_establecimiento='[CONFIGURAR DIRECCIÓN]',
                telefono='0000000000',
                correo='configurar@empresa.com',
                obligado='NO',
                tipo_regimen='GENERAL'
            )
            print(f"✅ Configuración básica creada para {empresa.razon_social}")
        except Exception as e:
            print(f"❌ Error creando configuración básica: {e}")
    
    # Cargar Clientes
    print("\n=== CARGANDO CLIENTES ===")
    clientes_data = [item for item in backup_data if item['model'] == 'inventario.cliente']
    
    for item in clientes_data:
        fields = item['fields']
        try:
            cliente, created = Cliente.objects.get_or_create(
                cedula=fields['cedula'],
                defaults={
                    'nombre': fields['nombre'],
                    'apellido': fields.get('apellido', ''),
                    'telefono': fields.get('telefono', ''),
                    'direccion': fields.get('direccion', ''),
                    'email': fields.get('email', ''),
                    'empresa': empresa,
                    'tipoCedula': fields.get('tipoCedula', '1'),
                    'tipoCliente': fields.get('tipoCliente', '1'),
                    'tipoRegimen': fields.get('tipoRegimen', '1'),
                    'tipoVenta': fields.get('tipoVenta', '1')
                }
            )
            
            if created:
                print(f"✅ Cliente creado: {cliente.nombre} ({cliente.cedula})")
                
        except Exception as e:
            print(f"❌ Error creando cliente {fields.get('cedula', 'N/A')}: {e}")
    
    # Cargar Productos
    print("\n=== CARGANDO PRODUCTOS ===")
    productos_data = [item for item in backup_data if item['model'] == 'inventario.producto']
    
    for item in productos_data:
        fields = item['fields']
        try:
            # Manejar campos decimales
            precio = Decimal(str(fields.get('precio', '0')))
            precio2 = None
            if fields.get('precio2'):
                precio2 = Decimal(str(fields['precio2']))
            costo_actual = Decimal(str(fields.get('costo_actual', '0')))
            
            producto, created = Producto.objects.get_or_create(
                nombre=fields['nombre'],
                defaults={
                    'codigo': fields.get('codigo', ''),
                    'codigo_barras': fields.get('codigo_barras', ''),
                    'precio': precio,
                    'precio2': precio2,
                    'costo_actual': costo_actual,
                    'iva': fields.get('iva', '2'),  # 12% por defecto
                    'stock': fields.get('stock', 0),
                    'precio_iva1': Decimal(str(fields.get('precio_iva1', '0'))),
                    'precio_iva2': Decimal(str(fields.get('precio_iva2', '0')))
                }
            )
            
            if created:
                print(f"✅ Producto creado: {producto.nombre}")
                
        except Exception as e:
            print(f"❌ Error creando producto {fields.get('nombre', 'N/A')}: {e}")
    
    # Cargar Secuencias si existen
    print("\n=== CARGANDO SECUENCIAS ===")
    secuencias_data = [item for item in backup_data if item['model'] == 'inventario.secuencia']
    
    for item in secuencias_data:
        fields = item['fields']
        try:
            secuencia, created = Secuencia.objects.get_or_create(
                tipo_documento=fields['tipo_documento'],
                establecimiento=fields['establecimiento'],
                punto_emision=fields['punto_emision'],
                defaults={
                    'descripcion': fields['descripcion'],
                    'secuencial': fields['secuencial'],
                    'activo': fields.get('activo', True),
                    'iva': fields.get('iva', True),
                    'fiscal': fields.get('fiscal', True),
                    'documento_electronico': fields.get('documento_electronico', True)
                }
            )
            
            if created:
                print(f"✅ Secuencia creada: {secuencia.descripcion}")
                
        except Exception as e:
            print(f"❌ Error creando secuencia: {e}")
    
    # Mostrar resumen
    print("\n=== RESUMEN FINAL ===")
    print(f"🏢 Empresas: {Empresa.objects.count()}")
    print(f"⚙️ Configuraciones: {Opciones.objects.count()}")
    print(f"👥 Clientes: {Cliente.objects.count()}")
    print(f"📦 Productos: {Producto.objects.count()}")
    print(f"🔢 Secuencias: {Secuencia.objects.count()}")
    print(f"👤 Usuarios: {Usuario.objects.count()}")
    
    # Verificar configuración
    try:
        config = Opciones.objects.get(empresa=empresa)
        print(f"\n✅ Configuración disponible para: {config.razon_social}")
        print(f"   RUC: {config.identificacion}")
        print(f"   Dirección: {config.direccion_establecimiento}")
        print(f"   Email: {config.correo}")
    except Opciones.DoesNotExist:
        print(f"\n❌ NO HAY CONFIGURACIÓN - Creando configuración básica...")
        Opciones.objects.create(
            empresa=empresa,
            identificacion=empresa.ruc,
            razon_social=empresa.razon_social,
            nombre_comercial=empresa.razon_social,
            direccion_establecimiento='[CONFIGURAR DIRECCIÓN]',
            telefono='0000000000',
            correo='configurar@empresa.com',
            obligado='NO',
            tipo_regimen='GENERAL'
        )
        print("✅ Configuración básica creada")

if __name__ == '__main__':
    cargar_todos_los_datos()
