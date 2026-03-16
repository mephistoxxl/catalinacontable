"""Generador RIDE (PDF) para Retencion usando el layout de Factura."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

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

        self.razon_social = (
            getattr(retencion, 'razon_social_sujeto', None)
            or getattr(proveedor, 'razon_social_proveedor', None)
            or getattr(proveedor, 'nombre_comercial_proveedor', None)
            or 'Sujeto retenido'
        )
        self.nombres = self.razon_social
        self.identificacion = (
            getattr(retencion, 'identificacion_sujeto', None)
            or getattr(proveedor, 'identificacion_proveedor', None)
            or ''
        )
        self.direccion = getattr(proveedor, 'direccion', '') or ''
        self.correo = getattr(proveedor, 'correo', '') or ''
        self.telefono = getattr(proveedor, 'telefono', '') or ''


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

        # Mantener el encabezado del RIDE consistente cuando ya fue autorizada.
        if (getattr(retencion, 'estado_sri', '') or '').upper() == 'AUTORIZADA':
            fecha_ref = getattr(retencion, 'actualizado_en', None)
            if fecha_ref:
                if timezone.is_aware(fecha_ref):
                    fecha_ref = timezone.localtime(fecha_ref)
                self.ride_fecha_autorizacion_text = fecha_ref.strftime('%d/%m/%Y %H:%M:%S')


class _DetalleRetencionAdapter:
    def __init__(self, detalle):
        base = f"{detalle.base_imponible:.2f}"
        porcentaje = f"{detalle.porcentaje_retener:.4f}"
        valor = f"{detalle.valor_retenido:.2f}"
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


class RIDERetencionGenerator:
    def __init__(self, retencion, opciones):
        self.retencion = retencion
        self.opciones = opciones

    def generar_pdf(self):
        factura_adapter = _RetencionFacturaAdapter(self.retencion)
        detalles = [_DetalleRetencionAdapter(d) for d in self.retencion.detalles.all().order_by('id')]

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
