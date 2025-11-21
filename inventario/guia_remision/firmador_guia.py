"""
Firmador de XML para Guías de Remisión - XAdES-BES
Completamente independiente del firmador de facturas
"""
import logging
from lxml import etree
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import base64
from datetime import datetime

logger = logging.getLogger(__name__)


class FirmadorGuiaRemision:
    """
    Firma digitalmente XMLs de Guías de Remisión con XAdES-BES
    """
    
    # Namespaces necesarios
    NS_DS = "http://www.w3.org/2000/09/xmldsig#"
    NS_XADES = "http://uri.etsi.org/01903/v1.3.2#"
    
    def __init__(self, archivo_p12, password_p12):
        """
        Inicializa el firmador con el certificado P12
        
        Args:
            archivo_p12: Ruta al archivo .p12 O contenido en bytes
            password_p12: Contraseña del archivo .p12
        """
        self.archivo_p12 = archivo_p12
        self.password_p12 = password_p12
        self.certificado = None
        self.clave_privada = None
        
        self._cargar_certificado()
    
    def _cargar_certificado(self):
        """Carga el certificado y clave privada desde el archivo P12"""
        try:
            # Soportar tanto ruta de archivo como contenido en bytes
            if isinstance(self.archivo_p12, bytes):
                p12_data = self.archivo_p12
            else:
                with open(self.archivo_p12, 'rb') as f:
                    p12_data = f.read()
            
            from cryptography.hazmat.primitives.serialization import pkcs12
            
            clave_privada, certificado, _ = pkcs12.load_key_and_certificates(
                p12_data,
                self.password_p12.encode() if isinstance(self.password_p12, str) else self.password_p12,
                backend=default_backend()
            )
            
            self.clave_privada = clave_privada
            self.certificado = certificado
            
            logger.info("Certificado cargado exitosamente para firmar guías de remisión")
            
        except Exception as e:
            logger.error(f"Error cargando certificado: {e}")
            raise
    
    def firmar_xml(self, xml_string):
        """
        Firma el XML de la guía de remisión con XAdES-BES
        
        Args:
            xml_string (str): XML sin firmar
            
        Returns:
            str: XML firmado
        """
        try:
            # Parsear XML
            root = etree.fromstring(xml_string.encode('utf-8'))
            
            # Calcular digest del documento
            c14n_xml = etree.tostring(root, method='c14n', exclusive=False)
            digest_value = self._calcular_digest(c14n_xml)
            
            # Crear nodo Signature
            signature = self._crear_signature(root, digest_value)
            
            # Calcular SignatureValue
            signed_info = signature.find(f"{{{self.NS_DS}}}SignedInfo")
            c14n_signed_info = etree.tostring(signed_info, method='c14n', exclusive=False)
            signature_value = self._firmar_datos(c14n_signed_info)
            
            # Agregar SignatureValue
            sig_value_elem = signature.find(f"{{{self.NS_DS}}}SignatureValue")
            sig_value_elem.text = signature_value
            
            # Agregar KeyInfo con certificado
            key_info = signature.find(f"{{{self.NS_DS}}}KeyInfo")
            self._agregar_certificado_a_keyinfo(key_info)
            
            # Agregar Signature al XML
            root.append(signature)
            
            # Convertir a string
            xml_firmado = etree.tostring(
                root,
                pretty_print=True,
                xml_declaration=True,
                encoding='UTF-8'
            ).decode('utf-8')
            
            logger.info("Guía de remisión firmada exitosamente")
            return xml_firmado
            
        except Exception as e:
            logger.error(f"Error firmando XML de guía de remisión: {e}")
            raise
    
    def _calcular_digest(self, data):
        """Calcula el digest SHA-256 de los datos"""
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(data)
        return base64.b64encode(digest.finalize()).decode('utf-8')
    
    def _firmar_datos(self, data):
        """Firma los datos con la clave privada"""
        firma = self.clave_privada.sign(
            data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(firma).decode('utf-8')
    
    def _crear_signature(self, root, digest_value):
        """Crea el nodo Signature con XAdES-BES"""
        signature = etree.Element(
            f"{{{self.NS_DS}}}Signature",
            nsmap={'ds': self.NS_DS, 'etsi': self.NS_XADES},
            Id="Signature"
        )
        
        # SignedInfo
        signed_info = etree.SubElement(signature, f"{{{self.NS_DS}}}SignedInfo")
        
        # CanonicalizationMethod
        canon_method = etree.SubElement(signed_info, f"{{{self.NS_DS}}}CanonicalizationMethod")
        canon_method.set('Algorithm', 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
        
        # SignatureMethod
        sig_method = etree.SubElement(signed_info, f"{{{self.NS_DS}}}SignatureMethod")
        sig_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#rsa-sha1')
        
        # Reference al documento
        reference = etree.SubElement(signed_info, f"{{{self.NS_DS}}}Reference")
        reference.set('URI', '#comprobante')
        
        transforms = etree.SubElement(reference, f"{{{self.NS_DS}}}Transforms")
        transform = etree.SubElement(transforms, f"{{{self.NS_DS}}}Transform")
        transform.set('Algorithm', 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
        
        digest_method = etree.SubElement(reference, f"{{{self.NS_DS}}}DigestMethod")
        digest_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
        
        digest_value_elem = etree.SubElement(reference, f"{{{self.NS_DS}}}DigestValue")
        digest_value_elem.text = digest_value
        
        # SignatureValue (vacío por ahora, se llenará después)
        sig_value = etree.SubElement(signature, f"{{{self.NS_DS}}}SignatureValue")
        sig_value.set('Id', 'SignatureValue')
        
        # KeyInfo (vacío por ahora, se llenará después)
        key_info = etree.SubElement(signature, f"{{{self.NS_DS}}}KeyInfo")
        key_info.set('Id', 'KeyInfo')
        
        # Object con XAdES
        obj = etree.SubElement(signature, f"{{{self.NS_DS}}}Object")
        obj.set('Id', 'Object')
        
        # QualifyingProperties
        qual_props = etree.SubElement(obj, f"{{{self.NS_XADES}}}QualifyingProperties")
        qual_props.set('Target', '#Signature')
        
        signed_props = etree.SubElement(qual_props, f"{{{self.NS_XADES}}}SignedProperties")
        signed_props.set('Id', 'SignedProperties')
        
        # SignedSignatureProperties
        signed_sig_props = etree.SubElement(signed_props, f"{{{self.NS_XADES}}}SignedSignatureProperties")
        
        signing_time = etree.SubElement(signed_sig_props, f"{{{self.NS_XADES}}}SigningTime")
        signing_time.text = datetime.now().strftime('%Y-%m-%dT%H:%M:%S-05:00')
        
        return signature
    
    def _agregar_certificado_a_keyinfo(self, key_info):
        """Agrega el certificado X509 al KeyInfo"""
        x509_data = etree.SubElement(key_info, f"{{{self.NS_DS}}}X509Data")
        x509_cert = etree.SubElement(x509_data, f"{{{self.NS_DS}}}X509Certificate")
        
        # Obtener certificado en formato PEM y extraer solo el base64
        cert_pem = self.certificado.public_bytes(serialization.Encoding.PEM).decode('utf-8')
        cert_base64 = cert_pem.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').strip()
        
        x509_cert.text = cert_base64
