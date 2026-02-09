"""Integración con el SRI para Notas de Débito Electrónicas."""

from __future__ import annotations

import logging
import os
import tempfile
import time
from datetime import datetime

from django.conf import settings

from inventario.models import Opciones

from .models import NotaDebito
from .xml_generator_nd import XMLGeneratorNotaDebito

logger = logging.getLogger(__name__)


class IntegracionSRINotaDebito:
    """Orquesta: generar XML, firmar, enviar y procesar respuesta SRI."""

    MAX_WAIT_SECONDS = 20
    RETRY_INTERVAL_SECONDS = 20

    def __init__(self, nota_debito: NotaDebito):
        self.nd = nota_debito
        self.empresa = nota_debito.empresa
        self.opciones = Opciones.objects.for_tenant(self.empresa).first()
        if not self.opciones:
            raise ValueError('No se encontró configuración de opciones para la empresa')

    def generar_xml(self) -> str:
        generator = XMLGeneratorNotaDebito(self.nd, self.opciones)
        if not self.nd.clave_acceso:
            self.nd.clave_acceso = generator.generar_clave_acceso()
            self.nd.save(update_fields=['clave_acceso'])
        return generator.generar_xml()

    def firmar_xml(self, xml_content: str) -> str:
        from inventario.sri.firmador_xades_sri import firmar_xml_xades_bes

        if not self.opciones.firma_electronica:
            raise ValueError('No hay firma electrónica configurada')
        if not self.opciones.password_firma:
            raise ValueError('No hay contraseña de firma configurada')

        xml_text = xml_content if isinstance(xml_content, str) else str(xml_content)

        with tempfile.TemporaryDirectory() as tmpdir:
            xml_in = os.path.join(tmpdir, f"nd_{self.nd.id}_sin_firmar.xml")
            xml_out = os.path.join(tmpdir, f"nd_{self.nd.id}_firmado.xml")

            with open(xml_in, 'w', encoding='utf-8') as f:
                f.write(xml_text)

            firmar_xml_xades_bes(xml_in, xml_out, empresa=self.empresa)

            with open(xml_out, 'r', encoding='utf-8') as f:
                return f.read()

    def enviar_sri(self, xml_firmado: str) -> dict:
        from inventario.sri.sri_client import SRIClient

        ambiente = 'pruebas' if self.opciones.tipo_ambiente == '1' else 'produccion'
        cliente = SRIClient(ambiente=ambiente)

        clave_acceso = self.nd.clave_acceso
        xml_text = xml_firmado if isinstance(xml_firmado, str) else str(xml_firmado)
        return cliente.procesar_comprobante_completo(xml_text, clave_acceso)

    def _es_clave_en_procesamiento(self, respuesta: dict) -> bool:
        if not isinstance(respuesta, dict):
            return False

        mensajes = respuesta.get('mensajes') or []
        texto = str(respuesta.get('raw_response') or respuesta)
        for msg in mensajes:
            if isinstance(msg, dict):
                cuerpo = f"{msg.get('mensaje', '')} {msg.get('informacionAdicional', '')}"
            else:
                cuerpo = str(msg)
            if 'EN PROCESAMIENTO' in cuerpo.upper():
                return True

        return 'EN PROCESAMIENTO' in texto.upper()

    def _actualizar_con_respuesta(self, respuesta: dict) -> str:
        estado = (respuesta or {}).get('estado')
        self.nd.estado_sri = estado or self.nd.estado_sri

        if estado == 'AUTORIZADO':
            autorizaciones = respuesta.get('autorizaciones') or []
            aut0 = autorizaciones[0] if isinstance(autorizaciones, list) and autorizaciones else {}

            numero_aut = (
                respuesta.get('numeroAutorizacion')
                or aut0.get('numeroAutorizacion')
                or self.nd.clave_acceso
            )
            self.nd.numero_autorizacion = numero_aut

            fecha_aut_raw = aut0.get('fechaAutorizacion') or respuesta.get('fechaAutorizacion')
            if fecha_aut_raw:
                fecha_aut_raw = str(fecha_aut_raw).strip()
                try:
                    self.nd.fecha_autorizacion = datetime.fromisoformat(fecha_aut_raw.replace('Z', '+00:00'))
                except Exception:
                    try:
                        self.nd.fecha_autorizacion = datetime.strptime(fecha_aut_raw, '%d/%m/%Y %H:%M:%S')
                    except Exception:
                        self.nd.fecha_autorizacion = None

            self.nd.mensaje_sri = 'Autorizado correctamente'
        else:
            self.nd.mensaje_sri = str(respuesta)[:2000]

        self.nd.save(update_fields=['estado_sri', 'mensaje_sri', 'numero_autorizacion', 'fecha_autorizacion'])
        return self.nd.estado_sri

    def procesar_completo(self) -> dict:
        """Flujo completo: generar XML, firmar, enviar y procesar respuesta."""
        try:
            xml = self.generar_xml()
            xml_firmado = self.firmar_xml(xml)
            respuesta = self.enviar_sri(xml_firmado)

            estado = (respuesta or {}).get('estado')
            if estado == 'DEVUELTA' and self._es_clave_en_procesamiento(respuesta):
                estado = 'PENDIENTE'
            else:
                estado = self._actualizar_con_respuesta(respuesta)

            pendientes = {
                'PENDIENTE',
                'EN_PROCESO',
                'EN_PROCESAMIENTO',
                'PROCESANDO',
                'PROCESAMIENTO',
                'RECIBIDA',
            }

            if estado in pendientes:
                from inventario.sri.sri_client import SRIClient

                ambiente = 'pruebas' if self.opciones.tipo_ambiente == '1' else 'produccion'
                cliente = SRIClient(ambiente=ambiente)

                inicio = time.time()
                while True:
                    elapsed = time.time() - inicio
                    if elapsed >= self.MAX_WAIT_SECONDS:
                        break

                    time.sleep(max(0, self.RETRY_INTERVAL_SECONDS))
                    resultado_auth = cliente.consultar_autorizacion(self.nd.clave_acceso)
                    estado = self._actualizar_con_respuesta(resultado_auth)
                    if estado == 'AUTORIZADO':
                        break

            return {
                'success': estado == 'AUTORIZADO',
                'estado': estado,
                'mensaje': self.nd.mensaje_sri,
                'clave_acceso': self.nd.clave_acceso,
                'numero_autorizacion': self.nd.numero_autorizacion,
            }
        except Exception as e:
            logger.exception('Error procesando Nota de Débito')
            try:
                self.nd.estado_sri = 'RECHAZADO'
                self.nd.mensaje_sri = str(e)
                self.nd.save(update_fields=['estado_sri', 'mensaje_sri'])
            except Exception:
                pass
            return {'success': False, 'estado': 'ERROR', 'mensaje': str(e)}
