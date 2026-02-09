"""Generador RIDE (PDF) para Nota de Debito usando el layout de Factura."""

from __future__ import annotations

from io import BytesIO

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


class _NotaDebitoFacturaAdapter:
    def __init__(self, nota_debito):
        self._nd = nota_debito
        self._factura = nota_debito.factura_modificada

        self.id = nota_debito.id
        self.clave_acceso = nota_debito.clave_acceso
        self.numero_autorizacion = nota_debito.numero_autorizacion
        self.fecha_autorizacion = nota_debito.fecha_autorizacion

        self.establecimiento = nota_debito.establecimiento
        self.punto_emision = nota_debito.punto_emision
        self.secuencia = nota_debito.secuencial
        self.establecimiento_formatted = str(nota_debito.establecimiento).zfill(3)
        self.punto_emision_formatted = str(nota_debito.punto_emision).zfill(3)
        self.secuencia_formatted = str(nota_debito.secuencial).zfill(9)

        self.ride_titulo = 'NOTA DE DEBITO'

        self.ambiente = getattr(nota_debito.empresa, 'tipo_ambiente', '1')
        self.tipo_emision = '1'

        self.fecha_emision = nota_debito.fecha_emision
        self.guia_remision = getattr(self._factura, 'guia_remision', '') if self._factura else ''

        self.cliente = getattr(self._factura, 'cliente', None)
        self.facturador = getattr(self._factura, 'facturador', None)

        self.total = nota_debito.valor_modificacion
        self.subtotal_sin_impuestos = nota_debito.subtotal_sin_impuestos
        self.subtotal_0 = None
        self.subtotal_no_objeto_iva = None
        self.subtotal_exento_iva = None
        self.descuento = None

        self.totales_impuestos = nota_debito.totales_impuestos
        self.formas_pago = _EmptyManager()

        self.empresa = nota_debito.empresa

        if self.fecha_autorizacion:
            fecha_aut = self.fecha_autorizacion
            if timezone.is_aware(fecha_aut):
                fecha_aut = timezone.localtime(fecha_aut)
            self.ride_fecha_autorizacion_text = fecha_aut.strftime('%d/%m/%Y %H:%M:%S')


class RIDENotaDebitoGenerator:
    def __init__(self, nota_debito, opciones):
        self.nd = nota_debito
        self.opciones = opciones

    def generar_pdf(self):
        factura_adapter = _NotaDebitoFacturaAdapter(self.nd)
        detalles = list(self.nd.detalles.all())

        ride = RIDEGenerator()
        pdf_bytes = ride.generar_ride_factura(
            factura_adapter,
            detalles,
            self.opciones,
            output_path='ride_nd.pdf',
            clave_acceso=self.nd.clave_acceso,
        )

        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        return buffer