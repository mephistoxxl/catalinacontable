"""Generador RIDE (PDF) para Nota de Credito usando el layout de Factura."""

from __future__ import annotations

from io import BytesIO
from datetime import datetime

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


class _NotaCreditoFacturaAdapter:
    def __init__(self, nota_credito):
        self._nc = nota_credito
        self._factura = nota_credito.factura_modificada

        self.id = nota_credito.id
        self.clave_acceso = nota_credito.clave_acceso
        self.numero_autorizacion = nota_credito.numero_autorizacion
        self.fecha_autorizacion = nota_credito.fecha_autorizacion

        self.establecimiento = nota_credito.establecimiento
        self.punto_emision = nota_credito.punto_emision
        self.secuencia = nota_credito.secuencial
        self.establecimiento_formatted = str(nota_credito.establecimiento).zfill(3)
        self.punto_emision_formatted = str(nota_credito.punto_emision).zfill(3)
        self.secuencia_formatted = str(nota_credito.secuencial).zfill(9)

        self.ride_titulo = 'NOTA DE CREDITO'

        self.ambiente = getattr(nota_credito.empresa, 'tipo_ambiente', '1')
        self.tipo_emision = '1'

        self.fecha_emision = nota_credito.fecha_emision
        self.guia_remision = getattr(self._factura, 'guia_remision', '') if self._factura else ''

        self.cliente = getattr(self._factura, 'cliente', None)
        self.facturador = getattr(self._factura, 'facturador', None)

        self.total = nota_credito.valor_modificacion
        self.subtotal_sin_impuestos = nota_credito.subtotal_sin_impuestos
        self.subtotal_0 = nota_credito.subtotal_iva_0
        self.subtotal_no_objeto_iva = nota_credito.subtotal_no_objeto_iva
        self.subtotal_exento_iva = nota_credito.subtotal_exento_iva
        self.descuento = nota_credito.total_descuento if hasattr(nota_credito, 'total_descuento') else None

        self.totales_impuestos = nota_credito.totales_impuestos
        self.formas_pago = _EmptyManager()

        self.empresa = nota_credito.empresa

        if self.fecha_autorizacion:
            fecha_aut = self.fecha_autorizacion
            if timezone.is_aware(fecha_aut):
                fecha_aut = timezone.localtime(fecha_aut)
            self.ride_fecha_autorizacion_text = fecha_aut.strftime('%d/%m/%Y %H:%M:%S')


class RIDEGeneratorNotaCredito:
    def __init__(self, nota_credito, opciones):
        self.nc = nota_credito
        self.opciones = opciones

    def generar_pdf(self):
        factura_adapter = _NotaCreditoFacturaAdapter(self.nc)
        detalles = list(self.nc.detalles.all())

        ride = RIDEGenerator()
        pdf_bytes = ride.generar_ride_factura(
            factura_adapter,
            detalles,
            self.opciones,
            output_path='ride_nc.pdf',
            clave_acceso=self.nc.clave_acceso,
        )

        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        return buffer