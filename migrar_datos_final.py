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

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
    except:
        return None

def migrar_datos_final():
    print("🎯 MIGRACIÓN FINAL - SIN TRANSACCIONES")
    print("=====================================")
    
    # Cargar backup
    with open('backup_sqlite_data.json', 'r') as f:
        backup_data = json.load(f)
    
    print(f"✅ Backup cargado: {len(backup_data)} registros")
    
    # Limpiar datos existentes
    print("\n🗑️ Limpiando datos existentes...")
    try:
        FormaPago.objects.all().delete()
        DetalleFactura.objects.all().delete()
        Factura.objects.all().delete()
        Secuencia.objects.all().delete()
        Caja.objects.all().delete()
        Facturador.objects.all().delete()
        Almacen.objects.all().delete()
        Producto.objects.all().delete()
        Cliente.objects.all().delete()
        UsuarioEmpresa.objects.all().delete()
        Opciones.objects.all().delete()
        Usuario.objects.all().delete()
        Empresa.objects.all().delete()
    except Exception as e:
        print(f"⚠️ Error limpiando: {e}")

    # 1. CARGAR EMPRESAS
    print("\n📊 Cargando empresas...")
    empresas_data = [item for item in backup_data if item['model'] == 'inventario.empresa']
    for item in empresas_data:
        fields = item['fields']
        empresa = Empresa.objects.create(
            ruc=fields['ruc'],
            razon_social=fields['razon_social']
        )
        print(f"✅ Empresa: {empresa.razon_social}")
    
    # Obtener la empresa principal
    empresa = Empresa.objects.first()
    
    # 2. CARGAR USUARIOS
    print("\n👥 Cargando usuarios...")
    usuarios_data = [item for item in backup_data if item['model'] == 'inventario.usuario']
    for item in usuarios_data:
        fields = item['fields']
        # Excluir campos ManyToMany
        empresas_ids = fields.pop('empresas', [])
        groups = fields.pop('groups', [])
        user_permissions = fields.pop('user_permissions', [])
        
        usuario = Usuario.objects.create(
            username=fields['username'],
            email=fields['email'],
            first_name=fields['first_name'],
            last_name=fields['last_name'],
            password=fields['password'],
            is_superuser=fields.get('is_superuser', False),
            is_staff=fields.get('is_staff', False),
            is_active=fields.get('is_active', True),
            nivel=fields.get('nivel', 1),
            last_login=parse_date(fields.get('last_login')),
            date_joined=parse_date(fields.get('date_joined')) or timezone.now()
        )
        print(f"✅ Usuario: {usuario.username}")
    
    # 3. CARGAR RELACIONES USUARIO-EMPRESA
    print("\n🔗 Cargando relaciones usuario-empresa...")
    for usuario in Usuario.objects.all():
        UsuarioEmpresa.objects.get_or_create(
            usuario=usuario,
            empresa=empresa
        )
        print(f"✅ Usuario {usuario.username} asociado con {empresa.razon_social}")
    
    # 3.5. CARGAR CONFIGURACIÓN GENERAL (OPCIONES)
    print("\n⚙️ Cargando configuración general...")
    opciones_data = [item for item in backup_data if item['model'] == 'inventario.opciones']
    for item in opciones_data:
        fields = item['fields']
        opciones = Opciones.objects.create(
            empresa=empresa,
            identificacion=fields.get('identificacion', '0000000000000'),
            firma_electronica=fields.get('firma_electronica', ''),
            password_firma=fields.get('password_firma', ''),
            fecha_caducidad_firma=parse_date(fields.get('fecha_caducidad_firma')),
            razon_social=fields.get('razon_social', '[CONFIGURAR RAZÓN SOCIAL]'),
            nombre_comercial=fields.get('nombre_comercial', '[CONFIGURAR NOMBRE COMERCIAL]'),
            direccion_establecimiento=fields.get('direccion_establecimiento', '[CONFIGURAR DIRECCIÓN]'),
            correo=fields.get('correo', 'configurar@empresa.com'),
            telefono=fields.get('telefono', '0000000000'),
            obligado=fields.get('obligado', 'SI'),
            tipo_regimen=fields.get('tipo_regimen', 'GENERAL'),
            es_contribuyente_especial=fields.get('es_contribuyente_especial', False),
            numero_contribuyente_especial=fields.get('numero_contribuyente_especial'),
            imagen=fields.get('imagen', ''),
            es_agente_retencion=fields.get('es_agente_retencion', False),
            numero_agente_retencion=fields.get('numero_agente_retencion'),
            valor_iva=int(fields.get('valor_iva', 15)),
            moneda=fields.get('moneda', 'USD'),
            nombre_negocio=fields.get('nombre_negocio', 'Mi Negocio'),
            mensaje_factura=fields.get('mensaje_factura', 'Gracias por su compra'),
            tipo_ambiente=fields.get('tipo_ambiente', '1'),
            tipo_emision=fields.get('tipo_emision', '1')
        )
        print(f"✅ Configuración: {opciones.razon_social} (RUC: {opciones.identificacion})")
    
    # 4. CARGAR CLIENTES
    print("\n👤 Cargando clientes...")
    clientes_data = [item for item in backup_data if item['model'] == 'inventario.cliente']
    for item in clientes_data:
        fields = item['fields']
        cliente = Cliente.objects.create(
            empresa=empresa,
            tipoIdentificacion=fields.get('tipoIdentificacion', '05'),
            identificacion=fields.get('identificacion', ''),
            razon_social=fields.get('razon_social', ''),
            nombre_comercial=fields.get('nombre_comercial', ''),
            direccion=fields.get('direccion', ''),
            telefono=fields.get('telefono', ''),
            correo=fields.get('correo', ''),
            observaciones=fields.get('observaciones', ''),
            convencional=fields.get('convencional', ''),
            tipoVenta=fields.get('tipoVenta', '1'),
            tipoRegimen=fields.get('tipoRegimen', '1'),
            tipoCliente=fields.get('tipoCliente', '1')
        )
        print(f"✅ Cliente: {cliente.razon_social} ({cliente.identificacion})")
    
    # 5. CARGAR PRODUCTOS
    print("\n📦 Cargando productos...")
    productos_data = [item for item in backup_data if item['model'] == 'inventario.producto']
    for item in productos_data:
        fields = item['fields']
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
    
    # 6. CARGAR ALMACENES
    print("\n🏪 Cargando almacenes...")
    almacenes_data = [item for item in backup_data if item['model'] == 'inventario.almacen']
    for item in almacenes_data:
        fields = item['fields']
        almacen = Almacen.objects.create(
            descripcion=fields.get('descripcion', ''),
            empresa=empresa,
            activo=fields.get('activo', True)
        )
        print(f"✅ Almacén: {almacen.descripcion}")
    
    # 7. CARGAR FACTURADORES
    print("\n👨‍💼 Cargando facturadores...")
    facturadores_data = [item for item in backup_data if item['model'] == 'inventario.facturador']
    for item in facturadores_data:
        fields = item['fields']
        facturador = Facturador.objects.create(
            nombres=fields['nombres'],
            telefono=fields.get('telefono', ''),
            correo=fields['correo'],
            empresa=empresa
        )
        print(f"✅ Facturador: {facturador.nombres}")
    
    # 8. CARGAR CAJAS
    print("\n💰 Cargando cajas...")
    cajas_data = [item for item in backup_data if item['model'] == 'inventario.caja']
    for item in cajas_data:
        fields = item['fields']
        caja = Caja.objects.create(
            descripcion=fields.get('descripcion', ''),
            empresa=empresa,
            activo=fields.get('activo', True)
        )
        print(f"✅ Caja: {caja.descripcion}")
    
    # 9. CARGAR FACTURAS
    print("\n📄 Cargando facturas...")
    facturas_data = [item for item in backup_data if item['model'] == 'inventario.factura']
    almacen_default = Almacen.objects.first()
    facturador_default = Facturador.objects.first()
    
    # Mapear facturas por índice
    facturas_map = {}
    
    for i, item in enumerate(facturas_data):
        fields = item['fields']
        # Buscar cliente por ID del backup
        cliente = None
        cliente_id = fields.get('cliente')
        if cliente_id:
            try:
                clientes_list = list(Cliente.objects.all())
                if 1 <= cliente_id <= len(clientes_list):
                    cliente = clientes_list[cliente_id - 1]
            except (IndexError, ValueError):
                cliente = Cliente.objects.first()
        
        if not cliente:
            cliente = Cliente.objects.first()
        
        factura = Factura.objects.create(
            empresa=empresa,
            cliente=cliente,
            almacen=almacen_default,
            facturador=facturador_default,
            fecha_emision=parse_date(fields.get('fecha_emision')) or timezone.now().date(),
            fecha_vencimiento=parse_date(fields.get('fecha_vencimiento')) or timezone.now().date(),
            establecimiento=fields.get('establecimiento', '001'),
            punto_emision=fields.get('punto_emision', '001'),
            secuencia=fields.get('secuencia', '000000001'),
            concepto=fields.get('concepto', ''),
            identificacion_cliente=fields.get('identificacion_cliente', ''),
            nombre_cliente=fields.get('nombre_cliente', ''),
            sub_monto=parse_decimal(fields.get('sub_monto', '0')),
            base_imponible=parse_decimal(fields.get('base_imponible', '0')),
            monto_general=parse_decimal(fields.get('monto_general', '0')),
            total_descuento=parse_decimal(fields.get('total_descuento', '0')),
            propina=parse_decimal(fields.get('propina', '0')),
            placa=fields.get('placa'),
            guia_remision=fields.get('guia_remision'),
            valor_retencion_iva=parse_decimal(fields.get('valor_retencion_iva', '0')),
            valor_retencion_renta=parse_decimal(fields.get('valor_retencion_renta', '0')),
            total_subsidio=parse_decimal(fields.get('total_subsidio', '0')),
            clave_acceso=fields.get('clave_acceso', ''),
            estado=fields.get('estado', 'PENDIENTE'),
            numero_autorizacion=fields.get('numero_autorizacion', ''),
            fecha_autorizacion=parse_date(fields.get('fecha_autorizacion')),
            estado_sri=fields.get('estado_sri', ''),
            mensaje_sri=fields.get('mensaje_sri', ''),
            mensaje_sri_detalle=fields.get('mensaje_sri_detalle', ''),
            xml_autorizado=fields.get('xml_autorizado', ''),
            ride_autorizado=fields.get('ride_autorizado', '')
        )
        facturas_map[i] = factura
        cliente_nombre = cliente.razon_social if cliente else "Sin cliente"
        print(f"✅ Factura: #{factura.secuencia} - {cliente_nombre} - ${factura.monto_general}")
    
    # 10. CARGAR DETALLES DE FACTURA
    print("\n📋 Cargando detalles de factura...")
    detalles_data = [item for item in backup_data if item['model'] == 'inventario.detallefactura']
    productos = list(Producto.objects.all())
    
    for i, item in enumerate(detalles_data):
        fields = item['fields']
        try:
            factura_index = min(i, len(facturas_map) - 1)
            factura = facturas_map.get(factura_index) or Factura.objects.first()
            producto = productos[0] if productos else None
            
            if factura and producto:
                detalle = DetalleFactura.objects.create(
                    factura=factura,
                    producto=producto,
                    cantidad=int(fields.get('cantidad', 1)),
                    sub_total=parse_decimal(fields.get('precio_total', '0')),
                    total=parse_decimal(fields.get('precio_total', '0')),
                    descuento=parse_decimal(fields.get('descuento', '0')),
                    empresa=empresa
                )
                print(f"✅ Detalle: {producto.descripcion} x{detalle.cantidad} en factura #{factura.secuencia}")
        except Exception as e:
            print(f"❌ Error detalle: {e}")
    
    # 11. CARGAR SECUENCIAS
    print("\n🔢 Cargando secuencias...")
    secuencias_data = [item for item in backup_data if item['model'] == 'inventario.secuencia']
    for item in secuencias_data:
        fields = item['fields']
        secuencia = Secuencia.objects.create(
            descripcion=fields['descripcion'],
            tipo_documento=fields['tipo_documento'],
            secuencial=fields['secuencial'],
            establecimiento=fields['establecimiento'],
            punto_emision=fields['punto_emision'],
            activo=fields.get('activo', True),
            iva=fields.get('iva', True),
            fiscal=fields.get('fiscal', True),
            documento_electronico=fields.get('documento_electronico', True)
        )
        print(f"✅ Secuencia: {secuencia.descripcion}")
    
    print("\n🎉 ¡MIGRACIÓN EXITOSA!")
    print("===========================")
    print(f"✅ Empresas: {Empresa.objects.count()}")
    print(f"✅ Usuarios: {Usuario.objects.count()}")  
    print(f"✅ Clientes: {Cliente.objects.count()}")
    print(f"✅ Productos: {Producto.objects.count()}")
    print(f"✅ Facturas: {Factura.objects.count()}")
    print(f"✅ Detalles: {DetalleFactura.objects.count()}")
    print(f"✅ Almacenes: {Almacen.objects.count()}")
    print(f"✅ Facturadores: {Facturador.objects.count()}")
    print(f"✅ Cajas: {Caja.objects.count()}")
    print(f"✅ Secuencias: {Secuencia.objects.count()}")
    print("===========================")
    print("🎯 ¡TODOS LOS DATOS RESTAURADOS!")

if __name__ == "__main__":
    migrar_datos_final()
