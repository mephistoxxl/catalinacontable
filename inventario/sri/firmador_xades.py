"""
Wrapper para firma XAdES-BES del SRI Ecuador.
Usa SOLO el firmador con estructura SRI exacta.
"""

import logging
from typing import Optional

from inventario.models import Empresa, Opciones

logger = logging.getLogger(__name__)


class XAdESError(Exception):
    """Error durante el proceso de firma XAdES-BES."""
    pass


def firmar_xml_xades_bes(
    xml_path: str,
    xml_firmado_path: str,
    *,
    empresa: Optional[Empresa] = None,
    opciones: Optional[Opciones] = None,
) -> bool:
    """
    Firma un XML con XAdES-BES usando estructura SRI exacta.
    
    Args:
        xml_path: Ruta al XML sin firmar
        xml_firmado_path: Ruta donde guardar el XML firmado
        empresa: Instancia de Empresa (opcional)
        opciones: Instancia de Opciones (opcional)
    
    Returns:
        bool: True si la firma fue exitosa
    
    Raises:
        XAdESError: Si ocurre algún error durante la firma
    """
    
    logger.info("🔥 Firmando XML con estructura SRI EXACTA")
    
    # Importar el firmador con estructura SRI
    from inventario.sri.firmador_xades_sri import firmar_xml_xades_bes_sri
    
    try:
        return firmar_xml_xades_bes_sri(
            xml_path,
            xml_firmado_path,
            empresa=empresa,
            opciones=opciones
        )
    except Exception as e:
        logger.error(f"❌ Error al firmar XML: {e}")
        raise XAdESError(f"Error al firmar XML: {e}") from e
