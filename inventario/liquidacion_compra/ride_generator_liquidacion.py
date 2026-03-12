from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from django.utils import timezone

from inventario.sri.ride_generator import RIDEGenerator


class _LiquidacionPartyAdapter:
    def __init__(self, liquidacion):
        prestador = getattr(liquidacion, 'prestador', None)
        proveedor = getattr(liquidacion, 'proveedor', None)

        self.razon_social = (
            getattr(prestador, 'nombre', None)
            or getattr(proveedor, 'razon_social_proveedor', None)
            or getattr(proveedor, 'nombre_comercial_proveedor', None)
            or 'Proveedor'
        )
        self.nombres = self.razon_social
        self.identificacion = (
            getattr(prestador, 'identificacion', None)
            or getattr(proveedor, 'identificacion_proveedor', None)
            or ''
        )
        self.direccion = (
            getattr(prestador, 'direccion', None)
            or getattr(proveedor, 'direccion', None)
            or ''
        )
        self.correo = (
            getattr(prestador, 'correo', None)
            or getattr(proveedor, 'correo', None)
            or ''
        )
        self.telefono = (
            getattr(prestador, 'telefono', None)
            or getattr(proveedor, 'telefono', None)
            or ''
        )


class _LiquidacionCompraAdapter:
    def __init__(self, liquidacion):
        self._liquidacion = liquidacion

        self.id = liquidacion.id
        self.clave_acceso = liquidacion.clave_acceso
        self.numero_autorizacion = liquidacion.numero_autorizacion
        self.fecha_autorizacion = liquidacion.fecha_autorizacion

        self.establecimiento = liquidacion.establecimiento
        self.punto_emision = liquidacion.punto_emision
        self.secuencia = liquidacion.secuencia
        self.establecimiento_formatted = str(liquidacion.establecimiento).zfill(3)
        self.punto_emision_formatted = str(liquidacion.punto_emision).zfill(3)
        self.secuencia_formatted = str(liquidacion.secuencia).zfill(9)

        self.ride_titulo = 'LIQUIDACIÓN DE COMPRA'
        self.ambiente = getattr(liquidacion.empresa, 'tipo_ambiente', '1')
        self.tipo_emision = '1'

        self.fecha_emision = liquidacion.fecha_emision
        self.guia_remision = ''
        self.cliente = _LiquidacionPartyAdapter(liquidacion)
        self.facturador = self._build_facturador(liquidacion)

        self.total = liquidacion.importe_total
        self.subtotal_sin_impuestos = liquidacion.total_sin_impuestos
        self.subtotal_0 = liquidacion.base_imponible_cero
        self.subtotal_no_objeto_iva = liquidacion.base_no_objeto
        self.subtotal_exento_iva = liquidacion.base_exenta
        self.descuento = liquidacion.total_descuento
        self.totales_impuestos = liquidacion.totales_impuestos
        self.formas_pago = liquidacion.formas_pago
        self.empresa = liquidacion.empresa

        if self.fecha_autorizacion:
            fecha_aut = self.fecha_autorizacion
            if timezone.is_aware(fecha_aut):
                fecha_aut = timezone.localtime(fecha_aut)
            self.ride_fecha_autorizacion_text = fecha_aut.strftime('%d/%m/%Y %H:%M:%S')

    def _build_facturador(self, liquidacion):
        usuario = getattr(liquidacion, 'usuario_creacion', None)
        if usuario is None:
            return SimpleNamespace(nombres='N/A')

        nombre = ' '.join(
            part for part in [getattr(usuario, 'first_name', ''), getattr(usuario, 'last_name', '')] if part
        ).strip()
        nombre = nombre or getattr(usuario, 'username', '') or 'N/A'
        return SimpleNamespace(nombres=nombre)


class RIDELiquidacionCompraGenerator:
    def __init__(self, liquidacion, opciones=None):
        self.liquidacion = liquidacion
        self.opciones = opciones or self._build_fallback_opciones(liquidacion)

    def _build_fallback_opciones(self, liquidacion):
        empresa = getattr(liquidacion, 'empresa', None)
        if empresa is None:
            return None

        return SimpleNamespace(
            imagen=None,
            razon_social=getattr(empresa, 'razon_social', '') or '',
            nombre_comercial='',
            direccion_matriz='',
            direccion_establecimiento='',
            contribuyente_especial='',
            obligado='NO',
            agente_retencion='',
            identificacion=getattr(empresa, 'ruc', '') or '',
            ambiente_descripcion=getattr(empresa, 'ambiente_descripcion', 'PRUEBAS'),
            correo='',
            telefono='',
        )

    def generar_pdf(self):
        adapter = _LiquidacionCompraAdapter(self.liquidacion)
        detalles = list(self.liquidacion.detalles.all())

        ride = RIDEGenerator()
        pdf_bytes = ride.generar_ride_factura(
            adapter,
            detalles,
            self.opciones,
            output_path='ride_liquidacion_compra.pdf',
            clave_acceso=self.liquidacion.clave_acceso,
        )

        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        return buffer