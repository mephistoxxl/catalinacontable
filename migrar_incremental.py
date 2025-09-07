#!/usr/bin/env python
"""
Migración INCREMENTAL (no borra nada, solo inserta lo faltante) desde backup_sqlite_data.json.
No modifica modelos. Usa claves lógicas para evitar duplicados.
"""
import os, json
from decimal import Decimal
from datetime import datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE','sistema.settings')
import django

django.setup()

from django.utils import timezone
from inventario.models import (
    Empresa, Usuario, UsuarioEmpresa, Opciones, Cliente, Proveedor, Producto,
    Almacen, Facturador, Caja, Banco, Factura, DetalleFactura, FormaPago, Secuencia
)

BACKUP = 'backup_sqlite_data.json'

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

def load_backup():
    if not os.path.exists(BACKUP):
        print('❌ No existe backup_sqlite_data.json')
        return []
    with open(BACKUP,'r',encoding='utf-8') as f:
        return json.load(f)

def ensure_empresa(items):
    emp_items=[x for x in items if x['model']=='inventario.empresa']
    if Empresa.objects.exists():
        e=Empresa.objects.first(); print(f"Empresa existente: {e.ruc}")
        return e
    for it in emp_items:
        f=it['fields']
        e=Empresa.objects.create(ruc=f.get('ruc'), razon_social=f.get('razon_social'))
        print(f"✅ Empresa creada {e.razon_social}")
        return e
    print('⚠️ No había empresa en backup y ninguna en BD')
    return None

def migrate_usuarios(items, empresa):
    usuarios=[x for x in items if x['model']=='inventario.usuario']
    for it in usuarios:
        f=it['fields']
        if Usuario.objects.filter(username=f['username']).exists():
            continue
        u=Usuario.objects.create(
            username=f['username'], email=f.get('email',''), first_name=f.get('first_name',''), last_name=f.get('last_name',''),
            password=f.get('password',''), is_superuser=f.get('is_superuser',False), is_staff=f.get('is_staff',False),
            is_active=f.get('is_active',True), nivel=f.get('nivel',1)
        )
        UsuarioEmpresa.objects.get_or_create(usuario=u, empresa=empresa)
        print(f"✅ Usuario {u.username}")

def migrate_opciones(items, empresa):
    if Opciones.objects.exists():
        return
    for it in items:
        if it['model']!='inventario.opciones': continue
        f=it['fields']
        Opciones.objects.create(
            empresa=empresa,
            identificacion=f.get('identificacion','0000000000000'),
            razon_social=f.get('razon_social',''), nombre_comercial=f.get('nombre_comercial',''),
            direccion_establecimiento=f.get('direccion_establecimiento',''), correo=f.get('correo',''), telefono=f.get('telefono',''),
            obligado=f.get('obligado','SI'), tipo_regimen=f.get('tipo_regimen','GENERAL'), valor_iva=int(f.get('valor_iva',15)),
            tipo_ambiente=f.get('tipo_ambiente','1'), tipo_emision=f.get('tipo_emision','1'), mensaje_factura=f.get('mensaje_factura','')
        )
        print('✅ Opciones creadas')
        break

def migrate_clientes(items, empresa):
    for it in items:
        if it['model']!='inventario.cliente': continue
        f=it['fields']
        ident=f.get('identificacion')
        if not ident or Cliente.objects.filter(identificacion=ident).exists():
            continue
        Cliente.objects.create(
            empresa=empresa, tipoIdentificacion=f.get('tipoIdentificacion','05'), identificacion=ident,
            razon_social=f.get('razon_social',''), nombre_comercial=f.get('nombre_comercial',''), direccion=f.get('direccion',''),
            telefono=f.get('telefono',''), correo=f.get('correo',''), observaciones=f.get('observaciones',''), convencional=f.get('convencional',''),
            tipoVenta=f.get('tipoVenta','1'), tipoRegimen=f.get('tipoRegimen','1'), tipoCliente=f.get('tipoCliente','1')
        )
        print(f"✅ Cliente {ident}")

def migrate_proveedores(items, empresa):
    for it in items:
        if it['model']!='inventario.proveedor': continue
        f=it['fields']
        ident=f.get('identificacion_proveedor')
        if not ident or Proveedor.objects.filter(identificacion_proveedor=ident).exists():
            continue
        Proveedor.objects.create(
            empresa=empresa, tipoIdentificacion=f.get('tipoIdentificacion','04'), identificacion_proveedor=ident,
            razon_social_proveedor=f.get('razon_social_proveedor',''), nombre_comercial_proveedor=f.get('nombre_comercial_proveedor',''),
            direccion=f.get('direccion',''), telefono=f.get('telefono',''), telefono2=f.get('telefono2',''), correo=f.get('correo',''), correo2=f.get('correo2',''),
            observaciones=f.get('observaciones',''), convencional=f.get('convencional',''), tipoVenta='1', tipoRegimen='1', tipoProveedor='1'
        )
        print(f"✅ Proveedor {ident}")

def migrate_productos(items, empresa):
    for it in items:
        if it['model']!='inventario.producto': continue
        f=it['fields']
        codigo=f.get('codigo')
        if not codigo or Producto.objects.filter(codigo=codigo, empresa=empresa).exists():
            continue
        Producto.objects.create(
            empresa=empresa, codigo=codigo, codigo_barras=f.get('codigo_barras',''), descripcion=f.get('descripcion',''),
            precio=parse_decimal(f.get('precio')), precio2=parse_decimal(f.get('precio2')) if f.get('precio2') else None,
            disponible=int(f.get('disponible',0)), categoria=f.get('categoria','1'), iva=f.get('iva','2'), costo_actual=parse_decimal(f.get('costo_actual','0')),
            precio_iva1=parse_decimal(f.get('precio_iva1','0')), precio_iva2=parse_decimal(f.get('precio_iva2','0'))
        )
        print(f"✅ Producto {codigo}")

def migrate_almacenes(items, empresa):
    for it in items:
        if it['model']!='inventario.almacen': continue
        f=it['fields']
        desc=f.get('descripcion') or f.get('numero') or 'Almacén'
        if Almacen.objects.filter(descripcion=desc, empresa=empresa).exists():
            continue
        Almacen.objects.create(empresa=empresa, descripcion=desc, activo=True)
        print(f"✅ Almacén {desc}")

def migrate_facturadores(items, empresa):
    for it in items:
        if it['model']!='inventario.facturador': continue
        f=it['fields']
        correo=f.get('correo')
        if not correo or Facturador.objects.filter(correo=correo).exists():
            continue
        Facturador.objects.create(empresa=empresa, nombres=f.get('nombres',''), telefono=f.get('telefono',''), correo=correo)
        print(f"✅ Facturador {correo}")

def migrate_cajas(items, empresa):
    for it in items:
        if it['model']!='inventario.caja': continue
        f=it['fields']
        desc=f.get('descripcion') or f.get('nombre') or 'Caja'
        if Caja.objects.filter(descripcion=desc, empresa=empresa).exists():
            continue
        Caja.objects.create(empresa=empresa, descripcion=desc, activo=True)
        print(f"✅ Caja {desc}")

def migrate_bancos(items, empresa):
    for it in items:
        if it['model']!='inventario.banco': continue
        f=it['fields']
        num=f.get('numero_cuenta')
        if not num or Banco.objects.filter(numero_cuenta=num).exists():
            continue
        Banco.objects.create(
            empresa=empresa, banco=f.get('banco','Banco'), titular=f.get('titular',''), numero_cuenta=num,
            activo=f.get('activo',True), saldo_inicial=parse_decimal(f.get('saldo_inicial','0')), tipo_cuenta=f.get('tipo_cuenta','AHORROS'),
            fecha_apertura=parse_date(f.get('fecha_apertura')), telefono=f.get('telefono',''), secuencial_cheque=f.get('secuencial_cheque',1),
            observaciones=f.get('observaciones','')
        )
        print(f"✅ Banco {num}")

def migrate_facturas(items, empresa):
    facturador = Facturador.objects.first()
    almacen = Almacen.objects.first()
    mapping={}
    for it in items:
        if it['model']!='inventario.factura': continue
        f=it['fields']
        clave=f.get('clave_acceso')
        if clave and Factura.objects.filter(clave_acceso=clave).exists():
            mapping[it['pk']] = Factura.objects.get(clave_acceso=clave)
            continue
        ident_cli=f.get('identificacion_cliente')
        cliente=Cliente.objects.filter(identificacion=ident_cli).first() or Cliente.objects.first()
        factura = Factura.objects.create(
            empresa=empresa, cliente=cliente, almacen=almacen, facturador=facturador,
            fecha_emision=parse_date(f.get('fecha_emision')) or timezone.now().date(),
            fecha_vencimiento=parse_date(f.get('fecha_vencimiento')) or timezone.now().date(),
            establecimiento=f.get('establecimiento','001'), punto_emision=f.get('punto_emision','001'), secuencia=f.get('secuencia','000000001'),
            concepto=f.get('concepto',''), identificacion_cliente=ident_cli or cliente.identificacion, nombre_cliente=f.get('nombre_cliente',''),
            sub_monto=parse_decimal(f.get('sub_monto')), base_imponible=parse_decimal(f.get('base_imponible')), monto_general=parse_decimal(f.get('monto_general')),
            total_descuento=parse_decimal(f.get('total_descuento')), propina=parse_decimal(f.get('propina')), placa=f.get('placa'), guia_remision=f.get('guia_remision'),
            valor_retencion_iva=parse_decimal(f.get('valor_retencion_iva')), valor_retencion_renta=parse_decimal(f.get('valor_retencion_renta')),
            total_subsidio=parse_decimal(f.get('total_subsidio')), clave_acceso=clave, estado=f.get('estado','PENDIENTE'),
            numero_autorizacion=f.get('numero_autorizacion'), fecha_autorizacion=None, estado_sri=f.get('estado_sri',''), mensaje_sri=f.get('mensaje_sri',''),
            mensaje_sri_detalle=f.get('mensaje_sri_detalle',''), xml_autorizado=f.get('xml_autorizado'), ride_autorizado=f.get('ride_autorizado') or None
        )
        mapping[it['pk']] = factura
        print(f"✅ Factura {factura.secuencia}")
    return mapping

def migrate_detalles(items, mapping, empresa):
    for it in items:
        if it['model']!='inventario.detallefactura': continue
        f=it['fields']
        old_fact=f.get('factura')
        factura=mapping.get(old_fact)
        if not factura: continue
        # Evitar duplicar detalles si ya existen detalles para esa factura
        if factura.detallefactura_set.exists():
            continue
        DetalleFactura.objects.create(
            empresa=empresa, factura=factura, producto=Producto.objects.first(), cantidad=int(f.get('cantidad',1)),
            sub_total=parse_decimal(f.get('sub_total','0')), total=parse_decimal(f.get('total','0')),
            descuento=parse_decimal(f.get('descuento','0')), porcentaje_descuento=parse_decimal(f.get('porcentaje_descuento','0')),
            servicio=None, precio_sin_subsidio=parse_decimal(f.get('precio_sin_subsidio')) if f.get('precio_sin_subsidio') else None
        )
        print(f"✅ Detalle factura {factura.secuencia}")

def migrate_formaspago(items, mapping, empresa):
    for it in items:
        if it['model']!='inventario.formapago': continue
        f=it['fields']
        factura=mapping.get(f.get('factura'))
        if not factura: continue
        total_fp=parse_decimal(f.get('total','0'))
        if FormaPago.objects.filter(factura=factura, forma_pago=f.get('forma_pago')).exists():
            continue
        # Ajustar total si excede
        pagado=sum(x.total for x in factura.formas_pago.all())
        restante=factura.monto_general - pagado
        if restante <= 0: continue
        if total_fp > restante: total_fp=restante
        FormaPago.objects.create(empresa=empresa, factura=factura, forma_pago=f.get('forma_pago','01'), total=total_fp, plazo=f.get('plazo'), unidad_tiempo=f.get('unidad_tiempo'))
        print(f"✅ FormaPago {f.get('forma_pago')} factura {factura.secuencia}")

def migrate_secuencias(items, empresa):
    for it in items:
        if it['model']!='inventario.secuencia': continue
        f=it['fields']
        if Secuencia.objects.filter(descripcion=f.get('descripcion'), tipo_documento=f.get('tipo_documento')).exists():
            continue
        Secuencia.objects.create(
            empresa=empresa, descripcion=f.get('descripcion',''), tipo_documento=f.get('tipo_documento','01'), secuencial=int(f.get('secuencial',1)),
            establecimiento=int(f.get('establecimiento',1)), punto_emision=int(f.get('punto_emision',1)), activo=f.get('activo',True), iva=f.get('iva',True), fiscal=f.get('fiscal',True), documento_electronico=f.get('documento_electronico',True)
        )
        print(f"✅ Secuencia {f.get('descripcion')}")

def main():
    items=load_backup()
    if not items: return
    empresa=ensure_empresa(items)
    if not empresa: return
    migrate_usuarios(items, empresa)
    migrate_opciones(items, empresa)
    migrate_clientes(items, empresa)
    migrate_proveedores(items, empresa)
    migrate_productos(items, empresa)
    migrate_almacenes(items, empresa)
    migrate_facturadores(items, empresa)
    migrate_cajas(items, empresa)
    migrate_bancos(items, empresa)
    mapping=migrate_facturas(items, empresa)
    migrate_detalles(items, mapping, empresa)
    migrate_formaspago(items, mapping, empresa)
    migrate_secuencias(items, empresa)
    print('\n✅ Migración incremental terminada')

if __name__=='__main__':
    main()
