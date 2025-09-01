# inventario/sri/firmador_xades.py
"""Utilidades de firma XAdES-BES basadas en endesive."""

import logging
from inventario.models import Opciones

logger = logging.getLogger(__name__)


class XAdESError(Exception):
    """Excepción personalizada para errores relacionados con XAdES."""
    pass


class SRIXAdESFirmador:
    """Firmador XAdES-BES sencillo respaldado por la librería endesive."""

    def __init__(self):
        self.opciones = Opciones.objects.filter(
            firma_electronica__isnull=False,
            password_firma__isnull=False,
        ).first()
        if not self.opciones:
            raise XAdESError(
                "Firma electrónica o contraseña no configuradas en Opciones"
            )

    def firmar_xml_xades_bes(self, xml_path: str, xml_firmado_path: str) -> bool:
        """Firma un XML usando XAdES-BES y guarda el resultado."""
        return firmar_xml_con_endesive(xml_path, xml_firmado_path)


def firmar_xml_xades_bes(xml_path: str, xml_firmado_path: str) -> bool:
    """Función de conveniencia para firmar un XML con XAdES-BES."""
    firmador = SRIXAdESFirmador()
    return firmador.firmar_xml_xades_bes(xml_path, xml_firmado_path)


def firmar_xml_con_endesive(xml_path: str, xml_firmado_path: str) -> bool:
    """Firma XML usando la implementación XAdES de la librería endesive."""
    try:
        from endesive.xml import xades
    except ImportError as e:
        msg = (
            "Librería endesive no disponible. "
            "Instale con `pip install endesive>=2.17.0`"
        )
        logger.error("%s: %s", msg, e)
        raise XAdESError(msg)

    opciones = Opciones.objects.filter(
        firma_electronica__isnull=False,
        password_firma__isnull=False,
    ).first()
    if not opciones:
        raise XAdESError("Firma electrónica o contraseña no configuradas")

    with open(xml_path, "rb") as f:
        xml_data = f.read()

    params = {
        "certificate": opciones.firma_electronica.path,
        "password": opciones.password_firma,
    }

    try:
        signature = xades.sign(xml_data, **params)
    except Exception as e:
        logger.error("Error con endesive: %s", e)
        raise XAdESError(f"Error en firma con endesive: {e}")

    with open(xml_firmado_path, "wb") as f:
        f.write(signature)

    logger.info("XML firmado con endesive XAdES-BES: %s", xml_firmado_path)
    return True
