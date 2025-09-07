#!/usr/bin/env python
"""
Migración completa desde backup_sqlite_data.json
Recrea todo el dominio en orden correcto con el esquema ACTUAL (FK Factura->Cliente.identificacion).
ADVERTENCIA: Elimina datos existentes.
"""
import os, json
from decimal import Decimal
from datetime import datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE','sistema.settings')
import django

django.setup()

from django.utils import timezone
from django.db import transaction
from inventario.models import (
    Empresa, Usuario, UsuarioEmpresa, Opciones, Cliente, Proveedor, Producto,
    Almacen, Facturador, Caja, Banco, Factura, DetalleFactura, FormaPago, Secuencia
)

BACKUP='backup_sqlite_data.json'

def parse_decimal(v, default='0.00'):
    if v in (None,''): v=default
    try: return Decimal(str(v))
    except: return Decimal(default)

def parse_date(v):
    if not v: return None
    for fmt in ('%Y-%m-%d','%Y-%m-%dT%H:%M:%S.%fZ','%Y-%m-%dT%H:%M:%SZ'):
        try: return datetime.strptime(v, fmt).date()
        except: pass
    return None

def parse_dt(v):
    if not v: return None
    for fmt in ('%Y-%m-%dT%H:%M:%S.%fZ','%Y-%m-%dT%H:%M:%SZ'):
        try: return datetime.strptime(v, fmt)
        except: pass
    return None

def main():
    if not os.path.exists(BACKUP):
        print('❌ No existe backup')
        return
    data=json.load(open(BACKUP,'r',encoding='utf-8'))
    print(f'📦 Registros en backup: {len(data)}')

    # LIMPIEZA ORDENADA
    print('\n🗑️ Eliminando datos existentes...')
    for model in [FormaPago, DetalleFactura, Factura, Secuencia, Banco, Caja, Facturador, Almacen, Producto, Proveedor, Cliente, Opciones, UsuarioEmpresa, Usuario, Empresa]:
        model.objects.all().delete()
    print('✅ Limpieza completa')

    # EMPRESA
    empresas = [x for x in data if x['model']=='inventario.empresa']
    for item in empresas:
        f=item['fields']
        e=Empresa.objects.create(ruc=f.get('ruc'), razon_social=f.get('razon_social'))
        print(f'✅ Empresa {e.razon_social}')
    empresa=Empresa.objects.first()

    # USUARIOS
    usuarios = [x for x in data if x['model']=='inventario.usuario']
    for it in usuarios:
        f=it['fields']
        Usuario.objects.create(
            username=f['username'], email=f.get('email',''), first_name=f.get('first_name',''), last_name=f.get('last_name',''),
            password=f.get('password',''), is_superuser=f.get('is_superuser',False), is_staff=f.get('is_staff',False),
            is_active=f.get('is_active',True), nivel=f.get('nivel',1)
        )
    for u in Usuario.objects.all():
        UsuarioEmpresa.objects.get_or_create(usuario=u, empresa=empresa)
    print(f'✅ Usuarios: {Usuario.objects.count()}')

    # OPCIONES
    for it in [x for x in data if x['model']=='inventario.opciones']:
        f=it['fields']
        Opciones.objects.create(
            empresa=empresa,
            identificacion=f.get('identificacion','0000000000000'),
            razon_social=f.get('razon_social',''), nombre_comercial=f.get('nombre_comercial',''),
            direccion_establecimiento=f.get('direccion_establecimiento',''), correo=f.get('correo',''), telefono=f.get('telefono',''),
            obligado=f.get('obligado','SI'), tipo_regimen=f.get('tipo_regimen','GENERAL'), valor_iva=int(f.get('valor_iva',15)),
            tipo_ambiente=f.get('tipo_ambiente','1'), tipo_emision=f.get('tipo_emision','1'), mensaje_factura=f.get('mensaje_factura','')
        )
    print(f'✅ Opciones: {Opciones.objects.count()}')

    # CLIENTES
    for it in [x for x in data if x['model']=='inventario.cliente']:
        f=it['fields']
        Cliente.objects.create(
            empresa=empresa, tipoIdentificacion=f.get('tipoIdentificacion','05'), identificacion=f.get('identificacion',''),
            razon_social=f.get('razon_social',''), nombre_comercial=f.get('nombre_comercial',''), direccion=f.get('direccion',''),
            telefono=f.get('telefono',''), correo=f.get('correo',''), observaciones=f.get('observaciones',''), convencional=f.get('convencional',''),
            tipoVenta=f.get('tipoVenta','1'), tipoRegimen=f.get('tipoRegimen','1'), tipoCliente=f.get('tipoCliente','1')
        )
    print(f'✅ Clientes: {Cliente.objects.count()}')

    # PROVEEDORES
    for it in [x for x in data if x['model']=='inventario.proveedor']:
        f=it['fields']
        Proveedor.objects.create(
            empresa=empresa, tipoIdentificacion=f.get('tipoIdentificacion','04'), identificacion_proveedor=f.get('identificacion_proveedor',''),
            razon_social_proveedor=f.get('razon_social_proveedor',''), nombre_comercial_proveedor=f.get('nombre_comercial_proveedor',''),
            direccion=f.get('direccion',''), telefono=f.get('telefono',''), telefono2=f.get('telefono2',''), correo=f.get('correo',''), correo2=f.get('correo2',''),
            observaciones=f.get('observaciones',''), convencional=f.get('convencional',''), tipoVenta='1', tipoRegimen='1', tipoProveedor='1'
        )
    print(f'✅ Proveedores: {Proveedor.objects.count()}')

    # PRODUCTOS
    productos=[x for x in data if x['model']=='inventario.producto']
    for it in productos:
        f=it['fields']
        Producto.objects.create(
            empresa=empresa, codigo=f.get('codigo',''), codigo_barras=f.get('codigo_barras',''), descripcion=f.get('descripcion',''),
            precio=parse_decimal(f.get('precio')), precio2=parse_decimal(f.get('precio2')) if f.get('precio2') else None,
            disponible=int(f.get('disponible',0)), categoria=f.get('categoria','1'), iva=f.get('iva','2'), costo_actual=parse_decimal(f.get('costo_actual','0')),
            precio_iva1=parse_decimal(f.get('precio_iva1','0')), precio_iva2=parse_decimal(f.get('precio_iva2','0'))
        )
    print(f'✅ Productos: {len(productos)}')

    # ALMACENES
    for it in [x for x in data if x['model']=='inventario.almacen']:
        f=it['fields']
        Almacen.objects.create(empresa=empresa, descripcion=f.get('descripcion', f.get('numero','Almacén')), activo=True)
    print(f'✅ Almacenes: {Almacen.objects.count()}')

    # FACTURADORES
    for it in [x for x in data if x['model']=='inventario.facturador']:
        f=it['fields']
        Facturador.objects.create(empresa=empresa, nombres=f.get('nombres',''), telefono=f.get('telefono',''), correo=f.get('correo',''))
    print(f'✅ Facturadores: {Facturador.objects.count()}')

    # CAJAS
    for it in [x for x in data if x['model']=='inventario.caja']:
        f=it['fields']
        Caja.objects.create(empresa=empresa, descripcion=f.get('descripcion', f.get('nombre','Caja')), activo=True)
    print(f'✅ Cajas: {Caja.objects.count()}')

    # BANCOS
    for it in [x for x in data if x['model']=='inventario.banco']:
        f=it['fields']
        Banco.objects.create(
            empresa=empresa, banco=f.get('banco','Banco'), titular=f.get('titular',''), numero_cuenta=f.get('numero_cuenta',''),
            activo=f.get('activo',True), saldo_inicial=parse_decimal(f.get('saldo_inicial','0')), tipo_cuenta=f.get('tipo_cuenta','AHORROS'),
            fecha_apertura=parse_date(f.get('fecha_apertura')), telefono=f.get('telefono',''), secuencial_cheque=f.get('secuencial_cheque',1),
            observaciones=f.get('observaciones','')
        )
    print(f'✅ Bancos: {Banco.objects.count()}')

    # FACTURAS
    facturas_backup=[x for x in data if x['model']=='inventario.factura']
    factura_map_old_new={}
    for it in facturas_backup:
        f=it['fields']
        ident_cli=f.get('identificacion_cliente')
        cliente = Cliente.objects.filter(identificacion=ident_cli).first() or Cliente.objects.first()
        facturador = Facturador.objects.first()
        almacen = Almacen.objects.first()
        factura = Factura.objects.create(
            empresa=empresa, cliente=cliente, almacen=almacen, facturador=facturador,
            fecha_emision=parse_date(f.get('fecha_emision')) or timezone.now().date(),
            fecha_vencimiento=parse_date(f.get('fecha_vencimiento')) or timezone.now().date(),
            establecimiento=f.get('establecimiento','001'), punto_emision=f.get('punto_emision','001'), secuencia=f.get('secuencia','000000001'),
            concepto=f.get('concepto',''), identificacion_cliente=ident_cli or cliente.identificacion, nombre_cliente=f.get('nombre_cliente',''),
            sub_monto=parse_decimal(f.get('sub_monto')), base_imponible=parse_decimal(f.get('base_imponible')), monto_general=parse_decimal(f.get('monto_general')),
            total_descuento=parse_decimal(f.get('total_descuento')), propina=parse_decimal(f.get('propina')), placa=f.get('placa'), guia_remision=f.get('guia_remision'),
            valor_retencion_iva=parse_decimal(f.get('valor_retencion_iva')), valor_retencion_renta=parse_decimal(f.get('valor_retencion_renta')),
            total_subsidio=parse_decimal(f.get('total_subsidio')), clave_acceso=f.get('clave_acceso'), estado=f.get('estado','PENDIENTE'),
            numero_autorizacion=f.get('numero_autorizacion'), fecha_autorizacion=None, estado_sri=f.get('estado_sri',''), mensaje_sri=f.get('mensaje_sri',''),
            mensaje_sri_detalle=f.get('mensaje_sri_detalle',''), xml_autorizado=f.get('xml_autorizado'), ride_autorizado=f.get('ride_autorizado') or None
        )
        factura_map_old_new[it['pk']] = factura
    print(f'✅ Facturas: {Factura.objects.count()}')

    # DETALLES FACTURA
    for it in [x for x in data if x['model']=='inventario.detallefactura']:
        f=it['fields']
        old_fk=f.get('factura')
        factura=factura_map_old_new.get(old_fk)
        if not factura: continue
        DetalleFactura.objects.create(
            empresa=empresa, factura=factura, producto=Producto.objects.first(), cantidad=int(f.get('cantidad',1)),
            sub_total=parse_decimal(f.get('sub_total','0')), total=parse_decimal(f.get('total','0')),
            descuento=parse_decimal(f.get('descuento','0')), porcentaje_descuento=parse_decimal(f.get('porcentaje_descuento','0')),
            servicio=None, precio_sin_subsidio=parse_decimal(f.get('precio_sin_subsidio')) if f.get('precio_sin_subsidio') else None
        )
    print(f'✅ Detalles: {DetalleFactura.objects.count()}')

    # FORMAS DE PAGO
    for it in [x for x in data if x['model']=='inventario.formapago']:
        f=it['fields']
        factura=factura_map_old_new.get(f.get('factura'))
        if not factura:
            continue
        if FormaPago.objects.filter(factura=factura, forma_pago=f.get('forma_pago')).exists():
            continue
        total_fp=parse_decimal(f.get('total','0'))
        # Si la factura tiene monto_general 0 (error de origen), usar total de forma de pago como monto_general y guardar
        if factura.monto_general == 0 and total_fp > 0:
            factura.monto_general = total_fp
            factura.sub_monto = total_fp
            factura.base_imponible = total_fp
            factura.save(update_fields=['monto_general','sub_monto','base_imponible'])
        # Evitar pasar límite: si excede, cap a restante
        pagado_existente=sum(fp.total for fp in factura.formas_pago.all())
        restante=factura.monto_general - pagado_existente
        if restante <= 0:
            continue
        if total_fp > restante:
            total_fp = restante
        FormaPago.objects.create(
            empresa=empresa,
            factura=factura,
            forma_pago=f.get('forma_pago','01'),
            total=total_fp,
            plazo=f.get('plazo'),
            unidad_tiempo=f.get('unidad_tiempo')
        )
    print(f'✅ FormasPago: {FormaPago.objects.count()}')

    # SECUENCIAS
    for it in [x for x in data if x['model']=='inventario.secuencia']:
        f=it['fields']
        if Secuencia.objects.filter(descripcion=f.get('descripcion'), tipo_documento=f.get('tipo_documento')).exists():
            continue
        Secuencia.objects.create(
            empresa=empresa, descripcion=f.get('descripcion',''), tipo_documento=f.get('tipo_documento','01'), secuencial=int(f.get('secuencial',1)),
            establecimiento=int(f.get('establecimiento',1)), punto_emision=int(f.get('punto_emision',1)), activo=f.get('activo',True), iva=f.get('iva',True), fiscal=f.get('fiscal',True), documento_electronico=f.get('documento_electronico',True)
        )
    print(f'✅ Secuencias: {Secuencia.objects.count()}')

    print('\n🎉 Migración COMPLETA finalizada')
    print('Resumen:')
    print(' Empresas:',Empresa.objects.count())
    print(' Usuarios:',Usuario.objects.count())
    print(' Clientes:',Cliente.objects.count())
    print(' Proveedores:',Proveedor.objects.count())
    print(' Productos:',Producto.objects.count())
    print(' Facturas:',Factura.objects.count())
    print(' Detalles:',DetalleFactura.objects.count())
    print(' FormasPago:',FormaPago.objects.count())
    print(' Bancos:',Banco.objects.count())
    print(' Secuencias:',Secuencia.objects.count())

if __name__=='__main__':
    main()
