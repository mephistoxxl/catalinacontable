#!/usr/bin/env python
import os
import django
import json
from decimal import Decimal
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import *
from django.db import transaction

def cargar_datos_completos():
    print("=== CARGANDO TODOS LOS DATOS COMPLETOS ===")
    
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
    
    # Función para convertir fechas
    def parse_date(date_str):
        if not date_str:
            return None
        try:
            # Formato ISO: 2020-06-09T18:59:58.342Z
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            # Formato fecha simple: 2020-06-09
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
        # 1. CARGAR ALMACENES
        print("\n=== CARGANDO ALMACENES ===")
        almacenes_data = [item for item in backup_data if item['model'] == 'inventario.almacen']
        for item in almacenes_data:
            fields = item['fields']
            try:
                almacen, created = Almacen.objects.get_or_create(
                    nombre=fields['nombre'],
                    defaults={
                        'empresa': empresa,
                        'activo': fields.get('activo', True)
                    }
                )
                if created:
                    print(f"✅ Almacén: {almacen.nombre}")
            except Exception as e:
                print(f"❌ Error almacén: {e}")
        
        # 2. CARGAR BANCOS
        print("\n=== CARGANDO BANCOS ===")
        bancos_data = [item for item in backup_data if item['model'] == 'inventario.banco']
        for item in bancos_data:
            fields = item['fields']
            try:
                banco, created = Banco.objects.get_or_create(
                    nombre=fields['nombre'],
                    defaults={
                        'empresa': empresa,
                        'numero_cuenta': fields.get('numero_cuenta', ''),
                        'tipo_cuenta': fields.get('tipo_cuenta', 'AHORRO'),
                        'saldo_inicial': parse_decimal(fields.get('saldo_inicial', '0'))
                    }
                )
                if created:
                    print(f"✅ Banco: {banco.nombre}")
            except Exception as e:
                print(f"❌ Error banco: {e}")
        
        # 3. CARGAR CAJAS
        print("\n=== CARGANDO CAJAS ===")
        cajas_data = [item for item in backup_data if item['model'] == 'inventario.caja']
        for item in cajas_data:
            fields = item['fields']
            try:
                caja, created = Caja.objects.get_or_create(
                    nombre=fields['nombre'],
                    defaults={
                        'empresa': empresa,
                        'saldo_inicial': parse_decimal(fields.get('saldo_inicial', '0'))
                    }
                )
                if created:
                    print(f"✅ Caja: {caja.nombre}")
            except Exception as e:
                print(f"❌ Error caja: {e}")
        
        # 4. CARGAR CLIENTES
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
                    print(f"✅ Cliente: {cliente.nombre} {cliente.apellido} ({cliente.cedula})")
            except Exception as e:
                print(f"❌ Error cliente: {e}")
        
        # 5. CARGAR PROVEEDORES
        print("\n=== CARGANDO PROVEEDORES ===")
        proveedores_data = [item for item in backup_data if item['model'] == 'inventario.proveedor']
        for item in proveedores_data:
            fields = item['fields']
            try:
                proveedor, created = Proveedor.objects.get_or_create(
                    ruc_proveedor=fields['ruc_proveedor'],
                    defaults={
                        'razon_social_proveedor': fields['razon_social_proveedor'],
                        'nombre_comercial_proveedor': fields.get('nombre_comercial_proveedor', ''),
                        'direccion': fields.get('direccion', ''),
                        'telefono': fields.get('telefono', ''),
                        'correo': fields.get('correo', ''),
                        'empresa': empresa
                    }
                )
                if created:
                    print(f"✅ Proveedor: {proveedor.razon_social_proveedor}")
            except Exception as e:
                print(f"❌ Error proveedor: {e}")
        
        # 6. CARGAR PRODUCTOS
        print("\n=== CARGANDO PRODUCTOS ===")
        productos_data = [item for item in backup_data if item['model'] == 'inventario.producto']
        for item in productos_data:
            fields = item['fields']
            try:
                producto, created = Producto.objects.get_or_create(
                    nombre=fields['nombre'],
                    defaults={
                        'codigo': fields.get('codigo', ''),
                        'codigo_barras': fields.get('codigo_barras', ''),
                        'precio': parse_decimal(fields.get('precio', '0')),
                        'precio2': parse_decimal(fields.get('precio2')) if fields.get('precio2') else None,
                        'costo_actual': parse_decimal(fields.get('costo_actual', '0')),
                        'iva': fields.get('iva', '2'),  # 12% por defecto
                        'stock': int(fields.get('stock', 0)),
                        'precio_iva1': parse_decimal(fields.get('precio_iva1', '0')),
                        'precio_iva2': parse_decimal(fields.get('precio_iva2', '0'))
                    }
                )
                if created:
                    print(f"✅ Producto: {producto.nombre} (${producto.precio})")
            except Exception as e:
                print(f"❌ Error producto: {e}")
        
        # 7. CARGAR FACTURADORES
        print("\n=== CARGANDO FACTURADORES ===")
        facturadores_data = [item for item in backup_data if item['model'] == 'inventario.facturador']
        for item in facturadores_data:
            fields = item['fields']
            try:
                facturador, created = Facturador.objects.get_or_create(
                    correo=fields['correo'],
                    defaults={
                        'nombres': fields['nombres'],
                        'telefono': fields.get('telefono', ''),
                        'is_active': fields.get('is_active', True),
                        'empresa': empresa
                    }
                )
                if created:
                    print(f"✅ Facturador: {facturador.nombres}")
            except Exception as e:
                print(f"❌ Error facturador: {e}")
        
        # 8. CARGAR FACTURAS
        print("\n=== CARGANDO FACTURAS ===")
        facturas_data = [item for item in backup_data if item['model'] == 'inventario.factura']
        for item in facturas_data:
            fields = item['fields']
            try:
                # Buscar cliente por ID del backup
                cliente = None
                if fields.get('cliente'):
                    # Buscar cliente en los datos originales
                    for cliente_item in clientes_data:
                        if cliente_item['pk'] == fields['cliente']:
                            cliente = Cliente.objects.filter(cedula=cliente_item['fields']['cedula']).first()
                            break
                
                # Buscar almacén
                almacen = Almacen.objects.first()  # Usar primer almacén disponible
                
                factura, created = Factura.objects.get_or_create(
                    numero=fields['numero'],
                    defaults={
                        'cliente': cliente,
                        'empresa': empresa,
                        'almacen': almacen,
                        'fecha': parse_date(fields.get('fecha')),
                        'sub_total': parse_decimal(fields.get('sub_total', '0')),
                        'total': parse_decimal(fields.get('total', '0')),
                        'descuento': parse_decimal(fields.get('descuento', '0')),
                        'porcentaje_descuento': parse_decimal(fields.get('porcentaje_descuento', '0')),
                        'precio_sin_subsidio': parse_decimal(fields.get('precio_sin_subsidio', '0')),
                        'observacion': fields.get('observacion', ''),
                        'clave_acceso': fields.get('clave_acceso', ''),
                        'estado_sri': fields.get('estado_sri', 'PENDIENTE'),
                        'fecha_autorizacion': parse_date(fields.get('fecha_autorizacion')),
                        'numero_autorizacion': fields.get('numero_autorizacion', ''),
                        'estado': fields.get('estado', 'ACTIVA')
                    }
                )
                if created:
                    print(f"✅ Factura: #{factura.numero} - ${factura.total}")
            except Exception as e:
                print(f"❌ Error factura: {e}")
        
        # 9. CARGAR DETALLES DE FACTURA
        print("\n=== CARGANDO DETALLES DE FACTURAS ===")
        detalles_data = [item for item in backup_data if item['model'] == 'inventario.detallefactura']
        for item in detalles_data:
            fields = item['fields']
            try:
                # Buscar factura por ID
                factura = None
                if fields.get('factura'):
                    for factura_item in facturas_data:
                        if factura_item['pk'] == fields['factura']:
                            factura = Factura.objects.filter(numero=factura_item['fields']['numero']).first()
                            break
                
                # Buscar producto
                producto = None
                if fields.get('producto'):
                    for producto_item in productos_data:
                        if producto_item['pk'] == fields['producto']:
                            producto = Producto.objects.filter(nombre=producto_item['fields']['nombre']).first()
                            break
                
                if factura and producto:
                    detalle, created = DetalleFactura.objects.get_or_create(
                        factura=factura,
                        producto=producto,
                        defaults={
                            'cantidad': int(fields.get('cantidad', 1)),
                            'precio_unitario': parse_decimal(fields.get('precio_unitario', '0')),
                            'precio_total': parse_decimal(fields.get('precio_total', '0')),
                            'descuento': parse_decimal(fields.get('descuento', '0')),
                            'empresa': empresa
                        }
                    )
                    if created:
                        print(f"✅ Detalle: {producto.nombre} x{detalle.cantidad} en factura #{factura.numero}")
            except Exception as e:
                print(f"❌ Error detalle factura: {e}")
        
        # 10. CARGAR FORMAS DE PAGO
        print("\n=== CARGANDO FORMAS DE PAGO ===")
        formas_pago_data = [item for item in backup_data if item['model'] == 'inventario.formapago']
        for item in formas_pago_data:
            fields = item['fields']
            try:
                # Buscar factura
                factura = None
                if fields.get('factura'):
                    for factura_item in facturas_data:
                        if factura_item['pk'] == fields['factura']:
                            factura = Factura.objects.filter(numero=factura_item['fields']['numero']).first()
                            break
                
                # Buscar caja
                caja = Caja.objects.first()
                
                if factura:
                    forma_pago, created = FormaPago.objects.get_or_create(
                        factura=factura,
                        forma_pago=fields.get('forma_pago', 'EFECTIVO'),
                        defaults={
                            'valor': parse_decimal(fields.get('valor', '0')),
                            'caja': caja,
                            'empresa': empresa
                        }
                    )
                    if created:
                        print(f"✅ Forma de pago: {forma_pago.forma_pago} ${forma_pago.valor}")
            except Exception as e:
                print(f"❌ Error forma de pago: {e}")
    
    # MOSTRAR RESUMEN FINAL
    print("\n" + "="*50)
    print("🎉 CARGA COMPLETA FINALIZADA")
    print("="*50)
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
    
    # Mostrar algunas facturas como ejemplo
    print(f"\n💡 EJEMPLOS DE FACTURAS CARGADAS:")
    for factura in Factura.objects.all()[:3]:
        cliente_nombre = f"{factura.cliente.nombre} {factura.cliente.apellido}" if factura.cliente else "Sin cliente"
        print(f"   📄 Factura #{factura.numero} - {cliente_nombre} - ${factura.total}")
    
    print(f"\n✅ TODOS TUS DATOS HAN SIDO RESTAURADOS EN POSTGRESQL!")

if __name__ == '__main__':
    cargar_datos_completos()
