from __future__ import annotations

import logging
from django.db import transaction

from ..sri.firmador_xades_sri_simple import FirmadorXAdESSRIEcuador
from ..sri.sri_client import SRIClient
from .models import RetencionCompra, RetencionLogCambioEstado
from .xml_generator_retencion import RetencionXMLGenerator

logger = logging.getLogger(__name__)


class IntegracionSRIRetencion:
    def __init__(self, empresa):
        self.empresa = empresa
        self.opciones = empresa.opciones.first() if hasattr(empresa, "opciones") else None
        if not self.opciones:
            raise ValueError("La empresa no tiene configuración de facturación electrónica.")

        ambiente = "produccion" if str(self.opciones.tipo_ambiente) == "2" else "pruebas"
        self.cliente_sri = SRIClient(ambiente=ambiente)
        self.xml_generator = RetencionXMLGenerator()

    def _registrar_log(self, retencion: RetencionCompra, estado: str, estado_sri: str, mensaje: str) -> None:
        try:
            RetencionLogCambioEstado.objects.create(
                retencion=retencion,
                estado=estado,
                estado_sri=estado_sri,
                mensaje=mensaje,
            )
        except Exception as exc:
            logger.warning("No se pudo registrar log de retención %s: %s", retencion.id, exc)

    def _firmar_xml(self, xml_content: str) -> dict:
        if not self.opciones.firma_electronica:
            return {"exito": False, "mensaje": "No hay firma electrónica configurada."}

        try:
            with self.opciones.firma_electronica.open("rb") as firma_file:
                p12_content = firma_file.read()
            firmador = FirmadorXAdESSRIEcuador(p12_content, self.opciones.password_firma)
            xml_firmado = firmador.firmar_xml(xml_content)
            return {"exito": True, "xml_firmado": xml_firmado}
        except Exception as exc:
            return {"exito": False, "mensaje": f"Error al firmar XML: {exc}"}

    def _aplicar_resultado_autorizacion(self, retencion: RetencionCompra, resultado: dict) -> dict:
        estado = (resultado.get("estado") or "").upper().strip()

        if estado == "AUTORIZADO":
            retencion.estado = "AUTORIZADA"
            retencion.estado_sri = "AUTORIZADO"
            retencion.numero_autorizacion = resultado.get("numero_autorizacion")
            retencion.fecha_autorizacion = resultado.get("fecha_autorizacion")
            retencion.xml_autorizado = resultado.get("xml_autorizado")
            retencion.mensaje_sri = "Comprobante autorizado"
            retencion.save(
                update_fields=[
                    "estado",
                    "estado_sri",
                    "numero_autorizacion",
                    "fecha_autorizacion",
                    "xml_autorizado",
                    "mensaje_sri",
                    "actualizado_en",
                ]
            )
            self._registrar_log(retencion, "AUTORIZADA", "AUTORIZADO", "Comprobante autorizado")
            return {"exito": True, "estado": "AUTORIZADO", "mensajes": ["Comprobante autorizado"]}

        if estado == "NO AUTORIZADO":
            retencion.estado = "RECHAZADA"
            retencion.estado_sri = "NO AUTORIZADO"
            retencion.mensaje_sri = "Comprobante no autorizado por SRI"
            retencion.save(update_fields=["estado", "estado_sri", "mensaje_sri", "actualizado_en"])
            self._registrar_log(retencion, "RECHAZADA", "NO AUTORIZADO", retencion.mensaje_sri)
            return {
                "exito": False,
                "estado": "NO AUTORIZADO",
                "mensajes": resultado.get("mensajes", []) or [retencion.mensaje_sri],
            }

        retencion.estado_sri = "PENDIENTE"
        retencion.mensaje_sri = "Pendiente de autorización"
        retencion.save(update_fields=["estado_sri", "mensaje_sri", "actualizado_en"])
        self._registrar_log(retencion, retencion.estado, "PENDIENTE", retencion.mensaje_sri)
        return {"exito": False, "estado": "PENDIENTE", "mensajes": resultado.get("mensajes", [])}

    def procesar_retencion_completa(self, retencion: RetencionCompra, *, enviar_solo: bool = False) -> dict:
        with transaction.atomic():
            if retencion.estado in {"AUTORIZADA", "RECHAZADA", "ANULADA"}:
                return {"exito": False, "estado": retencion.estado, "mensajes": ["Retención en estado final."]}

            if not retencion.clave_acceso:
                retencion.generar_clave_acceso()

            retencion.calcular_totales()
            retencion.save()

            xml = self.xml_generator.generar_xml_retencion(retencion)
            retencion.xml_generado = xml
            retencion.estado = "LISTA"
            retencion.save(update_fields=["clave_acceso", "codigo_interno", "xml_generado", "estado", "actualizado_en"])
            self._registrar_log(retencion, "LISTA", retencion.estado_sri or "", "XML de retención generado")

            firma = self._firmar_xml(xml)
            if not firma.get("exito"):
                retencion.estado = "RECHAZADA"
                retencion.estado_sri = "ERROR"
                retencion.mensaje_sri = firma.get("mensaje", "Error de firma")
                retencion.save(update_fields=["estado", "estado_sri", "mensaje_sri", "actualizado_en"])
                self._registrar_log(retencion, "RECHAZADA", "ERROR", retencion.mensaje_sri)
                return {"exito": False, "estado": "ERROR", "mensajes": [retencion.mensaje_sri]}

            retencion.xml_firmado = firma["xml_firmado"]
            retencion.estado = "FIRMADA"
            retencion.save(update_fields=["xml_firmado", "estado", "actualizado_en"])
            self._registrar_log(retencion, "FIRMADA", retencion.estado_sri or "", "XML firmado")

            envio = self.cliente_sri.enviar_comprobante(retencion.xml_firmado, retencion.clave_acceso)
            estado_envio = (envio.get("estado") or "").upper().strip()

            if estado_envio == "RECIBIDA":
                retencion.estado = "ENVIADA"
                retencion.estado_sri = "RECIBIDA"
                retencion.mensaje_sri = "Comprobante recibido por el SRI"
                retencion.save(update_fields=["estado", "estado_sri", "mensaje_sri", "actualizado_en"])
                self._registrar_log(retencion, "ENVIADA", "RECIBIDA", retencion.mensaje_sri)
                if enviar_solo:
                    return {"exito": True, "estado": "RECIBIDA", "mensajes": [retencion.mensaje_sri]}

                autorizacion = self.cliente_sri.consultar_autorizacion(retencion.clave_acceso)
                return self._aplicar_resultado_autorizacion(retencion, autorizacion)

            retencion.estado_sri = "PENDIENTE"
            retencion.mensaje_sri = "No se recibió confirmación RECIBIDA del SRI"
            retencion.save(update_fields=["estado_sri", "mensaje_sri", "actualizado_en"])
            self._registrar_log(retencion, retencion.estado, "PENDIENTE", retencion.mensaje_sri)
            return {
                "exito": False,
                "estado": "PENDIENTE",
                "mensajes": envio.get("mensajes", []) or [retencion.mensaje_sri],
            }

    def consultar_estado_actual(self, retencion: RetencionCompra) -> dict:
        if not retencion.clave_acceso:
            return {"exito": False, "estado": "ERROR", "mensajes": ["No existe clave de acceso."]}

        resultado = self.cliente_sri.consultar_autorizacion(retencion.clave_acceso)
        return self._aplicar_resultado_autorizacion(retencion, resultado)
