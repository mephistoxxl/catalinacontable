# inventario/sri/firmador.py

from signxml import XMLSigner, methods
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12
from inventario.models import Opciones

def firmar_xml(xml_path, xml_firmado_path):
    """
    🚫 FUNCIÓN OBSOLETA BLOQUEADA
    
    Esta función generaba firmas XMLDSig básicas que el SRI RECHAZA.
    Se ha bloqueado completamente para evitar envío de documentos inválidos.
    
    ❌ RAZÓN DEL BLOQUEO:
    - SRI exige XAdES-BES, no XMLDSig básico
    - Los documentos firmados con XMLDSig son RECHAZADOS
    - Puede causar problemas de cumplimiento fiscal
    
    ✅ SOLUCIÓN OBLIGATORIA:
    Usar: from inventario.sri.firmador_xades import firmar_xml_xades_bes
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.error("� ACCESO DENEGADO: Función firmar_xml() BLOQUEADA")
    logger.error("🚫 Esta función genera XMLDSig básico que SRI RECHAZA")
    logger.error("🚫 DEBE usar firmar_xml_xades_bes() en su lugar")
    
    raise Exception(
        "🚫 FUNCIÓN BLOQUEADA: firmar_xml() genera XMLDSig básico que SRI RECHAZA. "
        "DEBE usar: from inventario.sri.firmador_xades import firmar_xml_xades_bes"
    )


def firmar_xml_xades_experimental(xml_path, xml_firmado_path):
    """
    EXPERIMENTAL: Intento de firma XAdES-BES básica.
    
    ⚠️  ADVERTENCIA: Esta es una implementación experimental y puede no cumplir 
        completamente con todos los requisitos XAdES-BES del SRI.
    
    📋 Para producción, se recomienda usar una librería especializada en XAdES.
    """
    import hashlib
    from datetime import datetime
    
    opciones = Opciones.objects.first()
    if not opciones or not opciones.firma_electronica or not opciones.password_firma:
        raise Exception('Firma electrónica o contraseña no configuradas en Opciones')
    
    with open(opciones.firma_electronica.path, 'rb') as f:
        p12_data = f.read()
    
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
        p12_data, opciones.password_firma.encode()
    )
    
    # Convertir certificado y clave privada a PEM
    cert_pem = certificate.public_bytes(Encoding.PEM)
    key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    
    with open(xml_path, 'rb') as f:
        xml_data = f.read()
    root = etree.fromstring(xml_data)
    
    # Configurar XMLSigner con parámetros más específicos para XAdES
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm='rsa-sha256',
        digest_algorithm='sha256',
        c14n_algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
    )
    
    # Firmar con URI vacía (requerimiento SRI)
    signed_root = signer.sign(
        root,
        key=key_pem,
        cert=cert_pem,
        reference_uri=""  # ✅ CORREGIDO: URI="" explícita para SRI
    )
    
    # TODO: Agregar xades:QualifyingProperties aquí para XAdES-BES completo
    # Esto requeriría:
    # 1. xades:SignedProperties con timestamp
    # 2. xades:SigningCertificate con hash del certificado
    # 3. xades:SigningTime con timestamp ISO
    # 4. Namespace XAdES correctos
    
    with open(xml_firmado_path, 'wb') as f:
        f.write(etree.tostring(signed_root, pretty_print=True, xml_declaration=True, encoding='UTF-8'))


def _crear_qualifying_properties_xades(certificate, signing_time=None):
    """
    Crea las QualifyingProperties necesarias para XAdES-BES.
    
    ⚠️  EXPERIMENTAL: No implementado completamente.
    📋 TODO: Implementar según especificación XAdES v1.4.1
    """
    if signing_time is None:
        from datetime import datetime
        signing_time = datetime.utcnow()
    
    # Calcular hash del certificado
    import hashlib
    from cryptography.hazmat.primitives.serialization import Encoding
    cert_hash = hashlib.sha256(certificate.public_bytes(Encoding.DER)).digest()
    cert_hash_b64 = cert_hash.hex()
    
    # Plantilla XAdES-BES (simplificada)
    qualifying_props_template = f"""
    <xades:QualifyingProperties xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" Target="#signature">
        <xades:SignedProperties Id="signed-props">
            <xades:SignedSignatureProperties>
                <xades:SigningTime>{signing_time.isoformat()}Z</xades:SigningTime>
                <xades:SigningCertificate>
                    <xades:Cert>
                        <xades:CertDigest>
                            <ds:DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
                            <ds:DigestValue>{cert_hash_b64}</ds:DigestValue>
                        </xades:CertDigest>
                    </xades:Cert>
                </xades:SigningCertificate>
            </xades:SignedSignatureProperties>
        </xades:SignedProperties>
    </xades:QualifyingProperties>
    """
    
    return qualifying_props_template
