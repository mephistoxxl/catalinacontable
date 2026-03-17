"""Generador RIDE (PDF) para Retencion usando el layout de Factura."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from xml.sax.saxutils import escape

from django.utils import timezone

from inventario.sri.ride_generator import RIDEGenerator


class _EmptyManager:
    def __init__(self, items=None):
        self._items = list(items or [])

    def all(self):
        return self._items

    def exists(self):
        return bool(self._items)

    def count(self):
        return len(self._items)


class _RetencionPartyAdapter:
    def __init__(self, retencion):
        proveedor = getattr(retencion, 'proveedor', None)
        identificacion = (
            getattr(retencion, 'identificacion_sujeto', None)
            or getattr(proveedor, 'identificacion_proveedor', None)
            or ''
        )

        proveedor_lookup = None
        prestador_lookup = None
        cliente_lookup = None
        try:
            from inventario.models import Cliente, Proveedor
            from inventario.liquidacion_compra.models import Prestador

            if identificacion and getattr(retencion, 'empresa', None):
                qs_prov = Proveedor.objects.for_tenant(retencion.empresa) if hasattr(Proveedor.objects, 'for_tenant') else Proveedor.objects.filter(empresa=retencion.empresa)
                proveedor_lookup = qs_prov.filter(identificacion_proveedor=identificacion).first()

                qs_prest = Prestador.objects.for_tenant(retencion.empresa) if hasattr(Prestador.objects, 'for_tenant') else Prestador.objects.filter(empresa=retencion.empresa)
                prestador_lookup = qs_prest.filter(identificacion=identificacion).first()

                qs_cliente = Cliente.objects.for_tenant(retencion.empresa) if hasattr(Cliente.objects, 'for_tenant') else Cliente.objects.filter(empresa=retencion.empresa)
                cliente_lookup = qs_cliente.filter(identificacion=identificacion).first()
        except Exception:
            pass

        self.razon_social = (
            getattr(retencion, 'razon_social_sujeto', None)
            or getattr(proveedor, 'razon_social_proveedor', None)
            or getattr(proveedor, 'nombre_comercial_proveedor', None)
            or 'Sujeto retenido'
        )
        self.nombres = self.razon_social
        self.identificacion = (
            identificacion
        )
        self.direccion = (
            getattr(proveedor, 'direccion', '')
            or getattr(proveedor_lookup, 'direccion', '')
            or getattr(prestador_lookup, 'direccion', '')
            or getattr(cliente_lookup, 'direccion', '')
            or ''
        )
        self.correo = (
            getattr(proveedor, 'correo', '')
            or getattr(proveedor_lookup, 'correo', '')
            or getattr(prestador_lookup, 'correo', '')
            or getattr(cliente_lookup, 'correo', '')
            or getattr(cliente_lookup, 'email', '')
            or ''
        )
        self.telefono = (
            getattr(proveedor, 'telefono', '')
            or getattr(proveedor_lookup, 'telefono', '')
            or getattr(proveedor_lookup, 'telefono2', '')
            or getattr(prestador_lookup, 'telefono', '')
            or getattr(cliente_lookup, 'telefono', '')
            or ''
        )


class _RetencionFacturaAdapter:
    def __init__(self, retencion):
        self._retencion = retencion

        self.id = retencion.id
        self.clave_acceso = retencion.clave_acceso
        self.numero_autorizacion = retencion.numero_autorizacion or retencion.autorizacion_retencion
        self.fecha_autorizacion = None

        self.establecimiento = retencion.establecimiento_retencion
        self.punto_emision = retencion.punto_emision_retencion
        self.secuencia = retencion.secuencia_retencion
        self.establecimiento_formatted = str(retencion.establecimiento_retencion).zfill(3)
        self.punto_emision_formatted = str(retencion.punto_emision_retencion).zfill(3)
        self.secuencia_formatted = str(retencion.secuencia_retencion).zfill(9)

        self.ride_titulo = 'COMPROBANTE DE RETENCION'
        self.ambiente = getattr(retencion.empresa, 'tipo_ambiente', '1')
        self.tipo_emision = '1'

        self.fecha_emision = retencion.fecha_emision_retencion
        self.guia_remision = ''
        self.cliente = _RetencionPartyAdapter(retencion)

        usuario = getattr(retencion, 'usuario_creacion', None)
        nombre_usuario = 'N/A'
        if usuario:
            nombre_usuario = ' '.join(
                part for part in [getattr(usuario, 'first_name', ''), getattr(usuario, 'last_name', '')] if part
            ).strip() or getattr(usuario, 'username', '') or 'N/A'
        self.facturador = SimpleNamespace(nombres=nombre_usuario)

        self.total = retencion.total_retenido
        self.subtotal_sin_impuestos = retencion.total_retenido
        self.subtotal_0 = None
        self.subtotal_no_objeto_iva = None
        self.subtotal_exento_iva = None
        self.descuento = None

        self.totales_impuestos = _EmptyManager()
        self.formas_pago = _EmptyManager()
        self.empresa = retencion.empresa
        self.ride_total_label = 'TOTAL RETENIDO'
        self.ride_detalle_headers = [
            'Comprob ante',
            'Numero',
            'Fecha emision',
            'Ejercicio fiscal',
            'Base imponible',
            'Impuesto',
            'Codigo',
            '%Retencion',
            'Valor',
        ]
        self.ride_detalle_col_widths = [0.12, 0.14, 0.11, 0.11, 0.11, 0.09, 0.08, 0.10, 0.14]
        self.ride_detalle_numeric_cols = [4, 7, 8]

        info_lines = []
        direccion = getattr(self.cliente, 'direccion', '') or ''
        telefono = getattr(self.cliente, 'telefono', '') or ''
        correo = getattr(self.cliente, 'correo', '') or ''
        if direccion:
            info_lines.append(f"Dirección: {direccion}")
        if telefono:
            info_lines.append(f"Teléfono: {telefono}")
        if correo:
            info_lines.append(f"Email: {correo}")

        sanitized_lines = []
        for line in info_lines:
            if 'anfibius' in line.lower():
                continue
            sanitized_lines.append(escape(line))

        self.ride_info_adicional_text = '<br/>'.join(sanitized_lines)

        # Mantener el encabezado del RIDE consistente cuando ya fue autorizada.
        if (getattr(retencion, 'estado_sri', '') or '').upper() == 'AUTORIZADA':
            fecha_ref = getattr(retencion, 'actualizado_en', None)
            if fecha_ref:
                if timezone.is_aware(fecha_ref):
                    fecha_ref = timezone.localtime(fecha_ref)
                self.ride_fecha_autorizacion_text = fecha_ref.strftime('%d/%m/%Y %H:%M:%S')


class _DetalleRetencionAdapter:
    def __init__(self, detalle, retencion):
        base = f"{detalle.base_imponible:.2f}"
        porcentaje = f"{detalle.porcentaje_retener:.2f}"
        valor = f"{detalle.valor_retenido:.2f}"
        fecha_doc = getattr(retencion, 'fecha_emision', None)
        fecha_doc_txt = fecha_doc.strftime('%d/%m/%Y') if fecha_doc else ''
        ejercicio_fiscal = fecha_doc.strftime('%m/%Y') if fecha_doc else ''
        tipo_doc = {
            '01': 'FACTURA',
            '03': 'LIQUIDACION',
            '05': 'NOTA DE DEBITO',
        }.get(getattr(retencion, 'tipo_documento_sustento', ''), 'DOCUMENTO')
        numero_doc = (
            f"{str(getattr(retencion, 'establecimiento_doc', '001')).zfill(3)}"
            f"{str(getattr(retencion, 'punto_emision_doc', '001')).zfill(3)}"
            f"{str(getattr(retencion, 'secuencia_doc', '000000001')).zfill(9)}"
        )
        self.codigo_principal = f"{detalle.tipo_impuesto}-{detalle.codigo_retencion}"
        self.cantidad = 1
        self.unidad_medida = 'UND'
        self.descripcion = (
            detalle.descripcion_retencion
            or f"Retencion {detalle.tipo_impuesto} {detalle.codigo_retencion} | Base: {base} | %: {porcentaje} | Valor: {valor}"
        )
        self.precio_unitario = detalle.valor_retenido
        self.descuento = 0
        self.producto = None
        self.servicio = None
        self.ride_row_values = [
            tipo_doc,
            numero_doc,
            fecha_doc_txt,
            ejercicio_fiscal,
            base,
            detalle.tipo_impuesto,
            str(detalle.codigo_retencion),
            porcentaje,
            valor,
        ]


class RIDERetencionGenerator:
    def __init__(self, retencion, opciones):
        self.retencion = retencion
        self.opciones = opciones

    def generar_pdf(self):
        factura_adapter = _RetencionFacturaAdapter(self.retencion)
        detalles = [_DetalleRetencionAdapter(d, self.retencion) for d in self.retencion.detalles.all().order_by('id')]

        ride = RIDEGenerator()
        pdf_bytes = ride.generar_ride_factura(
            factura_adapter,
            detalles,
            self.opciones,
            output_path='ride_retencion.pdf',
            clave_acceso=self.retencion.clave_acceso,
        )

        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        return buffer
