# inventario/sri/firmador.py

from signxml import XMLSigner, methods
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12
from inventario.models import Opciones

def firmar_xml(xml_path, xml_firmado_path):
    """
    ⚠️  OBSOLETO: Firma un archivo XML usando XMLDSig básico.
    
    🚨 IMPORTANTE: Esta implementación usa XMLDSig básico, pero SRI requiere XAdES-BES.
    📋 ACCIÓN REQUERIDA: Migrar a firmador_xades.py que implementa XAdES-BES
    
    ❌ PROBLEMAS CONOCIDOS:
       - SRI puede RECHAZAR documentos firmados solo con XMLDSig
       - No incluye timestamp requerido por XAdES-BES
       - No incluye información del certificado como requiere SRI
    
    ✅ SOLUCIÓN: Usar firmar_xml_xades_bes() de firmador_xades.py
    
    📚 Librerías recomendadas para XAdES-BES:
       - firmador_xades.py: Implementación personalizada
       - endesive: Soporta XAdES-BES out-of-the-box
       - signxml + extensión manual para xades:QualifyingProperties
    
    Args:
        xml_path (str): Ruta al archivo XML a firmar.
        xml_firmado_path (str): Ruta donde se guardará el XML firmado.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("🚨 USANDO FIRMA XMLDSig BÁSICA - SRI PUEDE RECHAZAR ESTE DOCUMENTO")
    logger.warning("📋 Recomendación: Migrar a XAdES-BES usando firmador_xades.py")
    
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
    key_pem = private_key.private_bytes(
        Encoding.PEM,
        PrivateFormat.PKCS8,
        NoEncryption()
    )
    with open(xml_path, 'rb') as f:
        xml_data = f.read()
    root = etree.fromstring(xml_data)
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm='rsa-sha256',
        digest_algorithm='sha256',
        c14n_algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
    )
    
    # 🔧 CORREGIDO: Omitir reference_uri completamente para evitar error
    # signxml usa el comportamiento por defecto que es compatible con SRI
    signed_root = signer.sign(
        root,
        key=key_pem,
        cert=cert_pem
        # ✅ SIN reference_uri: Deja que signxml use el comportamiento por defecto
    )
    with open(xml_firmado_path, 'wb') as f:
        f.write(etree.tostring(signed_root, pretty_print=True, xml_declaration=True, encoding='UTF-8'))


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
