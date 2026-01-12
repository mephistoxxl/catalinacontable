"""Integración con el SRI para Notas de Débito Electrónicas."""

from __future__ import annotations

import logging
import os
import tempfile

from django.conf import settings

from inventario.models import Opciones

from .models import NotaDebito
from .xml_generator_nd import XMLGeneratorNotaDebito

logger = logging.getLogger(__name__)


class IntegracionSRINotaDebito:
    """Orquesta: generar XML, firmar, enviar y procesar respuesta SRI."""

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

    def procesar_completo(self) -> dict:
        """Flujo completo (placeholder)."""
        try:
            xml = self.generar_xml()
            xml_firmado = self.firmar_xml(xml)
            respuesta = self.enviar_sri(xml_firmado)

            estado = (respuesta or {}).get('estado')
            self.nd.estado_sri = estado or self.nd.estado_sri
            self.nd.mensaje_sri = str(respuesta)[:2000]
            self.nd.save(update_fields=['estado_sri', 'mensaje_sri'])

            return {
                'success': estado == 'AUTORIZADO',
                'estado': estado,
                'mensaje': self.nd.mensaje_sri,
                'clave_acceso': self.nd.clave_acceso,
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
