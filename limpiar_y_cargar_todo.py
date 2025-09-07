#!/usr/bin/env python
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import *
from django.db import transaction

def limpiar_y_cargar_todo():
    print("=== LIMPIANDO BASE DE DATOS Y CARGANDO TODO ===")
    
    with transaction.atomic():
        # Eliminar todos los datos (en orden inverso de dependencias)
        print("🗑️ Limpiando datos existentes...")
        FormaPago.objects.all().delete()
        DetalleFactura.objects.all().delete()
        Factura.objects.all().delete()
        Producto.objects.all().delete()
        Cliente.objects.all().delete()
        Proveedor.objects.all().delete()
        Facturador.objects.all().delete()
        Almacen.objects.all().delete()
        Banco.objects.all().delete()
        Caja.objects.all().delete()
        Opciones.objects.all().delete()
        UsuarioEmpresa.objects.all().delete()
        Usuario.objects.all().delete()
        Empresa.objects.all().delete()
        Secuencia.objects.all().delete()
        
        print("✅ Base de datos limpia")
    
    # Ahora cargar todos los datos usando Django loaddata
    print("📦 Cargando todos los datos originales...")
    
    try:
        from django.core.management import execute_from_command_line
        execute_from_command_line(['manage.py', 'loaddata', 'backup_sqlite_data.json'])
        print("✅ Datos cargados exitosamente")
    except Exception as e:
        print(f"❌ Error cargando datos: {e}")
        return
    
    # Verificar resultados
    print("\n" + "="*50)
    print("🎉 VERIFICACIÓN FINAL")
    print("="*50)
    print(f"🏢 Empresas: {Empresa.objects.count()}")
    print(f"👥 Usuarios: {Usuario.objects.count()}")
    print(f"👤 Clientes: {Cliente.objects.count()}")
    print(f"🏭 Proveedores: {Proveedor.objects.count()}")
    print(f"📦 Productos: {Producto.objects.count()}")
    print(f"📄 Facturas: {Factura.objects.count()}")
    print(f"📋 Detalles de Factura: {DetalleFactura.objects.count()}")
    print(f"💳 Formas de Pago: {FormaPago.objects.count()}")
    print(f"🏪 Almacenes: {Almacen.objects.count()}")
    print(f"🏦 Bancos: {Banco.objects.count()}")
    print(f"💰 Cajas: {Caja.objects.count()}")
    print(f"🔢 Secuencias: {Secuencia.objects.count()}")
    print(f"👨‍💼 Facturadores: {Facturador.objects.count()}")
    
    # Mostrar facturas como ejemplo
    print(f"\n💡 FACTURAS RESTAURADAS:")
    for factura in Factura.objects.all():
        cliente_nombre = f"{factura.cliente.nombre} {factura.cliente.apellido}" if factura.cliente else "Sin cliente"
        print(f"   📄 Factura #{factura.numero} - {cliente_nombre} - ${factura.total}")
    
    # Mostrar clientes
    print(f"\n👥 CLIENTES RESTAURADOS:")
    for cliente in Cliente.objects.all():
        print(f"   👤 {cliente.nombre} {cliente.apellido} - {cliente.cedula}")
    
    # Mostrar productos
    print(f"\n📦 PRODUCTOS RESTAURADOS:")
    for producto in Producto.objects.all():
        print(f"   📦 {producto.nombre} - ${producto.precio}")
    
    # Crear configuración básica si no existe
    empresa = Empresa.objects.first()
    if empresa and not Opciones.objects.filter(empresa=empresa).exists():
        print(f"\n⚙️ Creando configuración para {empresa.razon_social}...")
        Opciones.objects.create(
            empresa=empresa,
            identificacion=empresa.ruc,
            razon_social=empresa.razon_social,
            nombre_comercial=empresa.razon_social,
            direccion_establecimiento='Dirección Principal',
            telefono='0999999999',
            correo='admin@empresa.com',
            obligado='NO',
            tipo_regimen='GENERAL'
        )
        print("✅ Configuración creada")
    
    print(f"\n🎉 ¡TODOS TUS DATOS HAN SIDO RESTAURADOS COMPLETAMENTE!")
    print(f"   Puedes iniciar el servidor con: python manage.py runserver")

if __name__ == '__main__':
    limpiar_y_cargar_todo()
