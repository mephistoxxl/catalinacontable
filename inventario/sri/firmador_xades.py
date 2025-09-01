# inventario/sri/firmador_xades.py
"""Utilidades de firma XAdES-BES basadas en endesive.

Implementación actualizada usando endesive.xades (BES) con firma PKCS#12.
"""

import logging
from inventario.models import Opciones
from lxml import etree

# crypto
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

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
    """Firma XML usando la implementación XAdES de la librería endesive.

    Usa endesive.xades.BES.enveloped con una función de firmado basada en
    la llave privada del archivo PKCS#12 configurado en Opciones.
    """
    try:
        # API actual de endesive (no existe endesive.xml.xades en versiones recientes)
        from endesive.xades import BES
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

    # Leer XML fuente
    with open(xml_path, "rb") as f:
        xml_data = f.read()

    # Cargar PKCS#12 (p12/pfx)
    try:
        with open(opciones.firma_electronica.path, "rb") as pf:
            p12_bytes = pf.read()
        private_key, certificate, addl = pkcs12.load_key_and_certificates(
            p12_bytes, (opciones.password_firma or "").encode("utf-8")
        )
        if not private_key or not certificate:
            raise ValueError("No se pudo extraer llave o certificado del PKCS#12")
    except Exception as e:
        logger.error("Error leyendo PKCS#12: %s", e)
        raise XAdESError(f"Certificado PKCS#12 inválido: {e}")

    # Serializar certificado a DER
    try:
        cert_der = certificate.public_bytes(Encoding.DER)
    except Exception as e:
        logger.error("Error serializando certificado: %s", e)
        raise XAdESError(f"Error con certificado: {e}")

    # Función de firma para endesive (RSA + SHA256)
    def signproc(data: bytes, algo: str) -> bytes:
        try:
            return private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())
        except Exception as se:
            logger.error("Error firmando bytes canonizados: %s", se)
            raise

    # Construir XAdES-BES (enveloped)
    try:
        signer = BES()
        tree = signer.enveloped(
            xml_data,
            certificate,  # objeto x509
            cert_der,
            signproc,
            tspurl=None,
            tspcred=None,
        )
        signed_bytes = etree.tostring(
            tree, encoding="UTF-8", xml_declaration=True, standalone=False
        )
    except Exception as e:
        logger.error("Error con endesive: %s", e)
        raise XAdESError(f"Error en firma con endesive: {e}")

    # Guardar XML firmado
    with open(xml_firmado_path, "wb") as f:
        f.write(signed_bytes)

    logger.info("XML firmado con endesive XAdES-BES: %s", xml_firmado_path)
    return True
