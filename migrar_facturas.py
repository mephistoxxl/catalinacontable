#!/usr/bin/env python
"""
Script de migración SOLO para Facturas, Detalles y Formas de Pago
sin borrar lo existente. Usa el backup original (backup_sqlite_data.json)
y crea los registros faltantes en PostgreSQL mapeando referencias
por identificadores lógicos (identificación cliente, correo facturador,
descripción almacén, código de producto).

Se salta facturas ya existentes (clave_acceso única) y mantiene id internos nuevos.
"""
import os
import json
from decimal import Decimal
from datetime import datetime, date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
import django  # noqa: E402

django.setup()

from inventario.models import (
    Factura, DetalleFactura, FormaPago, Cliente, Producto, Facturador, Almacen, Empresa
)
from django.db import transaction
from django.utils import timezone

BACKUP_FILE = 'backup_sqlite_data.json'


def parse_decimal(v, default='0.00'):
    if v in (None, ''):
        v = default
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(default)


def parse_date(d):
    if not d:
        return None
    try:
        # Formato YYYY-MM-DD
        return datetime.strptime(d, '%Y-%m-%d').date()
    except Exception:
        try:
            return datetime.fromisoformat(d.replace('Z', '+00:00')).date()
        except Exception:
            return None


def load_backup():
    with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_lookup_maps(data):
    clientes_backup = {}
    productos_backup = {}
    facturadores_backup = {}
    almacenes_backup = {}

    for item in data:
        model = item.get('model')
        pk = item.get('pk')
        fields = item.get('fields', {})
        if model == 'inventario.cliente':
            clientes_backup[pk] = fields.get('identificacion'), fields
        elif model == 'inventario.producto':
            productos_backup[pk] = fields.get('codigo'), fields
        elif model == 'inventario.facturador':
            facturadores_backup[pk] = fields.get('correo'), fields
        elif model == 'inventario.almacen':
            # No tenemos campo codigo único; usaremos descripción
            almacenes_backup[pk] = fields.get('descripcion')
    return clientes_backup, productos_backup, facturadores_backup, almacenes_backup


def get_cliente_from_old_pk(old_pk, clientes_backup):
    ident = clientes_backup.get(old_pk, (None,))[0]
    if ident:
        return Cliente.objects.filter(identificacion=ident).first()
    return Cliente.objects.first()


def get_producto_from_old_pk(old_pk, productos_backup):
    codigo = productos_backup.get(old_pk, (None,))[0]
    if codigo:
        return Producto.objects.filter(codigo=codigo).first()
    return Producto.objects.first()


def get_facturador_from_list(lista_correos):
    if not lista_correos:
        return Facturador.objects.first()
    if isinstance(lista_correos, list):
        for correo in lista_correos:
            f = Facturador.objects.filter(correo=correo).first()
            if f:
                return f
    else:
        return Facturador.objects.filter(correo=lista_correos).first() or Facturador.objects.first()
    return Facturador.objects.first()


def get_almacen_from_old_pk(old_pk, almacenes_backup):
    desc = almacenes_backup.get(old_pk)
    if desc:
        a = Almacen.objects.filter(descripcion=desc).first()
        if a:
            return a
    return Almacen.objects.first()


def migrar_facturas():
    if not os.path.exists(BACKUP_FILE):
        print(f"❌ No existe {BACKUP_FILE}")
        return

    data = load_backup()
    clientes_backup, productos_backup, facturadores_backup, almacenes_backup = build_lookup_maps(data)

    empresa = Empresa.objects.first()
    if not empresa:
        print("❌ No hay Empresa cargada. Abortando.")
        return

    facturas_backup = [x for x in data if x.get('model') == 'inventario.factura']
    detalles_backup = [x for x in data if x.get('model') == 'inventario.detallefactura']
    formas_pago_backup = [x for x in data if x.get('model') == 'inventario.formapago']

    print(f"🔎 Facturas en backup: {len(facturas_backup)}")
    print(f"🔎 Detalles en backup: {len(detalles_backup)}")
    print(f"🔎 FormasPago en backup: {len(formas_pago_backup)}")
    # Debug clientes existentes
    print("👥 Clientes actuales:")
    for c in Cliente.objects.all():
        print(f"   id={c.id} ident={c.identificacion} razon={c.razon_social}")

    # Map old factura pk -> new factura instance
    factura_pk_map = {}

    creadas = 0
    saltadas = 0

    for item in facturas_backup:
        old_pk = item['pk']
        flds = item['fields']
        clave_acceso = flds.get('clave_acceso')

        # Evitar recrear si ya está la clave
        existente = None
        if clave_acceso:
            existente = Factura.objects.filter(clave_acceso=clave_acceso).first()
        if existente:
            factura_pk_map[old_pk] = existente
            saltadas += 1
            continue

    # Resolver cliente por identificación explícita (más robusto)
        identificacion_cli = flds.get('identificacion_cliente')
        cliente = None
        if identificacion_cli:
            cliente = Cliente.objects.filter(identificacion=identificacion_cli).first()
        if not cliente:
            # fallback a mapping por pk viejo
            cliente = get_cliente_from_old_pk(flds.get('cliente'), clientes_backup)
        if not cliente:
            cliente = Cliente.objects.first()

        # Validar existencia real en DB
        cliente_existe = Cliente.objects.filter(id=cliente.id).exists() if cliente else False
        if not cliente_existe:
            # intentar recrear a partir de identificación
            ident_crear = identificacion_cli or '0000000000'
            nombre_crear = flds.get('nombre_cliente') or 'CLIENTE MIGRADO'
            try:
                cliente = Cliente.objects.create(
                    empresa=empresa,
                    tipoIdentificacion='05',
                    identificacion=ident_crear[:13],
                    razon_social=nombre_crear[:200],
                    nombre_comercial=nombre_crear[:200],
                    direccion='[MIGRADO]',
                    telefono='',
                    correo='migrado@example.com',
                    observaciones='Creado automaticamente durante migración de facturas',
                    convencional='',
                    tipoVenta='1',
                    tipoRegimen='1',
                    tipoCliente='1'
                )
                print(f"🆕 Cliente fallback creado id={cliente.id} ident={cliente.identificacion}")
            except Exception as e:
                print(f"❌ No se pudo crear cliente fallback: {e}")
                cliente = Cliente.objects.first()

        print(f"➡️ Factura old_pk={old_pk} usando cliente id={cliente.id if cliente else 'None'} ident={cliente.identificacion if cliente else 'None'}")

        facturador = get_facturador_from_list(flds.get('facturador'))
        almacen = get_almacen_from_old_pk(flds.get('almacen'), almacenes_backup)

        fecha_emision = parse_date(flds.get('fecha_emision')) or timezone.now().date()
        fecha_venc = parse_date(flds.get('fecha_vencimiento')) or fecha_emision

        try:
            with transaction.atomic():
                factura = Factura.objects.create(
                    empresa=empresa,
                    cliente=cliente,
                    almacen=almacen,
                    facturador=facturador,
                    fecha_emision=fecha_emision,
                    fecha_vencimiento=fecha_venc,
                    establecimiento=flds.get('establecimiento', '001'),
                    punto_emision=flds.get('punto_emision', '001'),
                    secuencia=flds.get('secuencia', '000000001'),
                    concepto=flds.get('concepto') or '',
                    identificacion_cliente=identificacion_cli or (cliente.identificacion if cliente else ''),
                    nombre_cliente=flds.get('nombre_cliente') or (cliente.razon_social if cliente else ''),
                    sub_monto=parse_decimal(flds.get('sub_monto')),
                    base_imponible=parse_decimal(flds.get('base_imponible')),
                    monto_general=parse_decimal(flds.get('monto_general')),
                    total_descuento=parse_decimal(flds.get('total_descuento')),
                    propina=parse_decimal(flds.get('propina')),
                    placa=flds.get('placa'),
                    guia_remision=flds.get('guia_remision'),
                    valor_retencion_iva=parse_decimal(flds.get('valor_retencion_iva')),
                    valor_retencion_renta=parse_decimal(flds.get('valor_retencion_renta')),
                    total_subsidio=parse_decimal(flds.get('total_subsidio')),
                    clave_acceso=clave_acceso,
                    estado=flds.get('estado', 'PENDIENTE') or 'PENDIENTE',
                    numero_autorizacion=flds.get('numero_autorizacion'),
                    fecha_autorizacion=None,
                    estado_sri=flds.get('estado_sri', '') or '',
                    mensaje_sri=flds.get('mensaje_sri'),
                    mensaje_sri_detalle=flds.get('mensaje_sri_detalle'),
                    xml_autorizado=flds.get('xml_autorizado'),
                    ride_autorizado=flds.get('ride_autorizado') or None,
                )
                factura_pk_map[old_pk] = factura
                creadas += 1
                print(f"✅ Factura creada {factura.secuencia} ({factura.estado_sri})")
        except Exception as e:
            print(f"❌ Error creando factura pk_old={old_pk}: {e}")

    print(f"➡️ Facturas creadas: {creadas} | saltadas (existían): {saltadas}")

    # DETALLES
    detalles_creados = 0
    for item in detalles_backup:
        f = item['fields']
        old_factura_pk = f.get('factura')
        factura = factura_pk_map.get(old_factura_pk)
        if not factura:
            continue
        producto = get_producto_from_old_pk(f.get('producto'), productos_backup)
        if not producto:
            producto = Producto.objects.first()
        try:
            with transaction.atomic():
                DetalleFactura.objects.create(
                    empresa=factura.empresa,
                    factura=factura,
                    producto=producto,
                    cantidad=int(f.get('cantidad', 1)),
                    sub_total=parse_decimal(f.get('sub_total')),
                    total=parse_decimal(f.get('total')),
                    descuento=parse_decimal(f.get('descuento')),
                    porcentaje_descuento=parse_decimal(f.get('porcentaje_descuento')),
                    servicio=None,
                    precio_sin_subsidio=parse_decimal(f.get('precio_sin_subsidio')) if f.get('precio_sin_subsidio') else None,
                )
                detalles_creados += 1
        except Exception as e:
            print(f"❌ Error detalle factura_old={old_factura_pk}: {e}")
    print(f"➡️ Detalles creados: {detalles_creados}")

    # FORMAS DE PAGO (si el modelo existe y la clave de acceso coincide)
    formas_creadas = 0
    if FormaPago.objects.exists():
        for item in formas_pago_backup:
            flds = item['fields']
            old_factura_pk = flds.get('factura')
            factura = factura_pk_map.get(old_factura_pk)
            if not factura:
                continue
            # Evitar duplicados por total mismo
            if FormaPago.objects.filter(factura=factura, total=parse_decimal(flds.get('total'))).exists():
                continue
            try:
                FormaPago.objects.create(
                    empresa=factura.empresa,
                    factura=factura,
                    forma_pago=flds.get('forma_pago', '01'),
                    caja=None,  # opcional; si se requiere se puede mapear
                    total=parse_decimal(flds.get('total')),
                    plazo=flds.get('plazo'),
                    unidad_tiempo=flds.get('unidad_tiempo')
                )
                formas_creadas += 1
            except Exception as e:
                print(f"❌ Error forma pago factura_old={old_factura_pk}: {e}")
    print(f"➡️ Formas de pago creadas: {formas_creadas}")

    print("\n🎉 Migración de facturas completada")


if __name__ == '__main__':
    migrar_facturas()
