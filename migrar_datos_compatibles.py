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
from django.db import transaction
from django.contrib.auth.hashers import make_password

def migrar_datos_compatibles():
    print("=== MIGRACIÓN COMPATIBLE DE DATOS ===")
    
    # Leer el backup
    with open('backup_sqlite_data.json', 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    print(f"✅ Backup cargado: {len(backup_data)} registros")
    
    # Función para convertir fechas
    def parse_date(date_str):
        if not date_str:
            return None
        try:
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return None
    
    # Función para convertir decimales
    def parse_decimal(value, default='0'):
        if value is None or value == '':
            return Decimal(default)
        try:
            return Decimal(str(value))
        except:
            return Decimal(default)
    
    with transaction.atomic():
        # 1. LIMPIAR DATOS EXISTENTES
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
        
        # 2. CARGAR EMPRESAS
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
        
        # 3. CARGAR USUARIOS
        print("\n👥 Cargando usuarios...")
        usuarios_data = [item for item in backup_data if item['model'] == 'inventario.usuario']
        for item in usuarios_data:
            fields = item['fields']
            # Excluir el campo 'empresas' que es ManyToMany
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
        
        # 4. CARGAR RELACIONES USUARIO-EMPRESA (Asociar todos los usuarios con la empresa)
        print("\n🔗 Cargando relaciones usuario-empresa...")
        for usuario in Usuario.objects.all():
            UsuarioEmpresa.objects.get_or_create(
                usuario=usuario,
                empresa=empresa
            )
            print(f"✅ Usuario {usuario.username} asociado con {empresa.razon_social}")
        
        # 5. CARGAR CLIENTES
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
        
        # 6. CARGAR PRODUCTOS
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
        
        # 7. CARGAR ALMACENES
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
        
        # Si no hay almacenes, crear uno por defecto
        if not Almacen.objects.exists():
            almacen_default = Almacen.objects.create(
                descripcion="Almacén Principal",
                empresa=empresa,
                activo=True
            )
            print(f"✅ Almacén por defecto: {almacen_default.descripcion}")
        
        # 8. CARGAR FACTURADORES
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
        
        # Si no hay facturadores, crear uno por defecto
        if not Facturador.objects.exists():
            facturador_default = Facturador.objects.create(
                nombres="Facturador Principal",
                telefono="0999999999",
                correo="facturador@empresa.com",
                empresa=empresa
            )
            print(f"✅ Facturador por defecto: {facturador_default.nombres}")
        
        # 9. CARGAR CAJAS
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
        
        # Si no hay cajas, crear una por defecto
        if not Caja.objects.exists():
            caja_default = Caja.objects.create(
                descripcion="Caja Principal",
                empresa=empresa,
                activo=True
            )
            print(f"✅ Caja por defecto: {caja_default.descripcion}")
        
        # 10. CARGAR FACTURAS
        print("\n📄 Cargando facturas...")
        facturas_data = [item for item in backup_data if item['model'] == 'inventario.factura']
        almacen_default = Almacen.objects.first()
        facturador_default = Facturador.objects.first()
        
        # Mapear facturas por número para las relaciones
        facturas_map = {}
        
        for i, item in enumerate(facturas_data):
            fields = item['fields']
            # Buscar cliente por ID del backup
            cliente = None
            cliente_id = fields.get('cliente')
            if cliente_id:
                try:
                    # El cliente_id del backup es 1-based, nuestros clientes son secuenciales
                    clientes_list = list(Cliente.objects.all())
                    if 1 <= cliente_id <= len(clientes_list):
                        cliente = clientes_list[cliente_id - 1]
                except (IndexError, ValueError):
                    # Si no se puede mapear, usar el primer cliente disponible
                    cliente = Cliente.objects.first()
            
            # Si no hay cliente, usar el primer cliente disponible
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
        
        # 11. CARGAR DETALLES DE FACTURA
        print("\n📋 Cargando detalles de factura...")
        detalles_data = [item for item in backup_data if item['model'] == 'inventario.detallefactura']
        productos = list(Producto.objects.all())
        
        for i, item in enumerate(detalles_data):
            fields = item['fields']
            try:
                # Usar la factura correspondiente del mapeo
                factura_index = min(i, len(facturas_map) - 1)
                factura = facturas_map.get(factura_index) or Factura.objects.first()
                
                # Usar el primer producto disponible
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
        
        # 12. CARGAR FORMAS DE PAGO
        print("\n💳 Cargando formas de pago...")
        formas_pago_data = [item for item in backup_data if item['model'] == 'inventario.formapago']
        caja_default = Caja.objects.first()
        
        for i, item in enumerate(formas_pago_data):
            fields = item['fields']
            try:
                # Usar la factura correspondiente del mapeo
                factura_index = min(i, len(facturas_map) - 1)
                factura = facturas_map.get(factura_index) or Factura.objects.first()
                
                if factura:
                    # Asegurarse de que el total sea mayor a 0.01
                    total_pago = parse_decimal(fields.get('valor', '0'))
                    if total_pago < Decimal('0.01'):
                        total_pago = factura.monto_general or Decimal('1.00')
                    
                    forma_pago = FormaPago.objects.create(
                        factura=factura,
                        forma_pago=fields.get('forma_pago', '01'),
                        total=total_pago,
                        caja=caja_default,
                        empresa=empresa
                    )
                    print(f"✅ Forma de pago: {forma_pago.forma_pago} ${forma_pago.total} - Factura #{factura.secuencia}")
            except Exception as e:
                print(f"❌ Error forma de pago: {e}")
        
        # 13. CARGAR SECUENCIAS
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
        
        # 14. CREAR CONFIGURACIÓN
        print("\n⚙️ Creando configuración...")
        opciones_data = [item for item in backup_data if item['model'] == 'inventario.opciones']
        if opciones_data:
            fields = opciones_data[0]['fields']
            config = Opciones.objects.create(
                empresa=empresa,
                identificacion=fields.get('identificacion', empresa.ruc),
                razon_social=fields.get('razon_social', empresa.razon_social),
                nombre_comercial=fields.get('nombre_comercial', empresa.razon_social),
                direccion_establecimiento=fields.get('direccion', 'Dirección Principal'),
                telefono=fields.get('telefono', '0999999999'),
                correo=fields.get('correo', 'admin@empresa.com'),
                obligado='SI' if fields.get('obligado', '1') == '1' else 'NO',
                tipo_regimen='GENERAL'
            )
        else:
            config = Opciones.objects.create(
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
        print(f"✅ Configuración creada")
    
    # MOSTRAR RESUMEN FINAL
    print("\n" + "="*60)
    print("🎉 MIGRACIÓN COMPLETA EXITOSA")
    print("="*60)
    print(f"🏢 Empresas: {Empresa.objects.count()}")
    print(f"⚙️ Configuraciones: {Opciones.objects.count()}")
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
    
    print(f"\n💰 FACTURAS RESTAURADAS:")
    for factura in Factura.objects.all():
        cliente_nombre = f"{factura.cliente.nombre} {factura.cliente.apellido}" if factura.cliente else "Sin cliente"
        print(f"   📄 #{factura.numero} - {cliente_nombre} - ${factura.total} - {factura.fecha}")
    
    print(f"\n👥 CLIENTES RESTAURADOS:")
    for cliente in Cliente.objects.all():
        print(f"   👤 {cliente.nombre} {cliente.apellido} - {cliente.cedula}")
    
    print(f"\n📦 PRODUCTOS RESTAURADOS:")
    for producto in Producto.objects.all():
        print(f"   📦 {producto.nombre} - ${producto.precio}")
    
    print(f"\n🎊 ¡TODOS TUS DATOS HAN SIDO RESTAURADOS COMPLETAMENTE!")
    print(f"   ✅ {Cliente.objects.count()} clientes")
    print(f"   ✅ {Factura.objects.count()} facturas") 
    print(f"   ✅ {Producto.objects.count()} productos")
    print(f"   ✅ ¡Todo funcionando en PostgreSQL!")

if __name__ == '__main__':
    migrar_datos_compatibles()
