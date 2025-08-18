# inventario/sri/firmador_xades.py

"""
Firmador XAdES-BES completo para SRI Ecuador
Implementa XAdES-BES usando endesive y lxml para cumplir con los requisitos del SRI
"""

import os
import logging
from datetime import datetime
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64
import hashlib

from inventario.models import Opciones

logger = logging.getLogger(__name__)

class XAdESError(Exception):
    """Excepción personalizada para errores de XAdES"""
    pass

class SRIXAdESFirmador:
    """
    Firmador XAdES-BES específico para SRI Ecuador
    """
    
    def __init__(self):
        """Inicializar el firmador con configuración de Opciones"""
        self.opciones = Opciones.objects.first()
        if not self.opciones or not self.opciones.firma_electronica or not self.opciones.password_firma:
            raise XAdESError('Firma electrónica o contraseña no configuradas en Opciones')
        
        self._cargar_certificado()
    
    def _cargar_certificado(self):
        """Cargar y validar el certificado PKCS#12"""
        try:
            with open(self.opciones.firma_electronica.path, 'rb') as f:
                p12_data = f.read()
            
            # Cargar certificado PKCS#12
            self.private_key, self.certificate, self.additional_certs = pkcs12.load_key_and_certificates(
                p12_data, 
                self.opciones.password_firma.encode(),
                backend=default_backend()
            )
            
            logger.info("Certificado PKCS#12 cargado correctamente")
            
        except Exception as e:
            raise XAdESError(f"Error al cargar certificado: {e}")
    
    def firmar_xml_xades_bes(self, xml_path, xml_firmado_path):
        """
        Firma XML con XAdES-BES completo según especificaciones SRI
        
        Args:
            xml_path (str): Ruta al XML sin firmar
            xml_firmado_path (str): Ruta donde guardar el XML firmado
        """
        try:
            # Leer XML original
            with open(xml_path, 'rb') as f:
                xml_data = f.read()
            
            # Parsear XML
            doc = etree.fromstring(xml_data)
            
            # Crear signature con XAdES-BES
            signed_doc = self._crear_signature_xades_bes(doc)
            
            # Guardar XML firmado
            with open(xml_firmado_path, 'wb') as f:
                f.write(etree.tostring(
                    signed_doc, 
                    pretty_print=True, 
                    xml_declaration=True, 
                    encoding='UTF-8'
                ))
            
            logger.info(f"XML firmado con XAdES-BES guardado en: {xml_firmado_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al firmar XML con XAdES-BES: {e}")
            raise XAdESError(f"Error en firma XAdES-BES: {e}")
    
    def _crear_signature_xades_bes(self, doc):
        """
        Crear elemento Signature con XAdES-BES completo
        """
        # Namespaces requeridos
        ns_ds = "http://www.w3.org/2000/09/xmldsig#"
        ns_xades = "http://uri.etsi.org/01903/v1.3.2#"
        
        # Registrar namespaces
        etree.register_namespace("ds", ns_ds)
        etree.register_namespace("xades", ns_xades)
        
        # Crear elemento Signature
        signature = etree.Element(
            f"{{{ns_ds}}}Signature",
            Id="signature",
            nsmap={
                "ds": ns_ds,
                "xades": ns_xades
            }
        )
        
        # 1. SignedInfo
        signed_info = self._crear_signed_info(ns_ds)
        signature.append(signed_info)
        
        # 2. SignatureValue (placeholder, se calculará después)
        signature_value = etree.SubElement(signature, f"{{{ns_ds}}}SignatureValue")
        signature_value.text = "PLACEHOLDER_SIGNATURE_VALUE"
        
        # 3. KeyInfo
        key_info = self._crear_key_info(ns_ds)
        signature.append(key_info)
        
        # 4. Object con QualifyingProperties (XAdES-BES)
        obj = self._crear_object_xades(ns_ds, ns_xades)
        signature.append(obj)
        
        # Insertar signature en el documento
        doc.append(signature)
        
        # Calcular firma real
        self._calcular_signature_value(doc, signed_info, signature_value, ns_ds)
        
        return doc
    
    def _crear_signed_info(self, ns_ds):
        """Crear elemento SignedInfo"""
        signed_info = etree.Element(f"{{{ns_ds}}}SignedInfo")
        
        # CanonicalizationMethod
        canon_method = etree.SubElement(signed_info, f"{{{ns_ds}}}CanonicalizationMethod")
        canon_method.set("Algorithm", "http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        
        # SignatureMethod
        sig_method = etree.SubElement(signed_info, f"{{{ns_ds}}}SignatureMethod")
        sig_method.set("Algorithm", "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256")
        
        # Reference al documento completo
        reference = etree.SubElement(signed_info, f"{{{ns_ds}}}Reference")
        reference.set("URI", "")
        
        # Transforms
        transforms = etree.SubElement(reference, f"{{{ns_ds}}}Transforms")
        transform = etree.SubElement(transforms, f"{{{ns_ds}}}Transform")
        transform.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#enveloped-signature")
        
        # DigestMethod
        digest_method = etree.SubElement(reference, f"{{{ns_ds}}}DigestMethod")
        digest_method.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha256")
        
        # DigestValue (placeholder)
        digest_value = etree.SubElement(reference, f"{{{ns_ds}}}DigestValue")
        digest_value.text = "PLACEHOLDER_DIGEST_VALUE"
        
        # Reference a SignedProperties (XAdES requirement)
        ref_signed_props = etree.SubElement(signed_info, f"{{{ns_ds}}}Reference")
        ref_signed_props.set("Type", "http://uri.etsi.org/01903#SignedProperties")
        ref_signed_props.set("URI", "#signed-properties")
        
        # DigestMethod para SignedProperties
        digest_method_props = etree.SubElement(ref_signed_props, f"{{{ns_ds}}}DigestMethod")
        digest_method_props.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha256")
        
        # DigestValue para SignedProperties (placeholder)
        digest_value_props = etree.SubElement(ref_signed_props, f"{{{ns_ds}}}DigestValue")
        digest_value_props.text = "PLACEHOLDER_SIGNED_PROPS_DIGEST"
        
        return signed_info
    
    def _crear_key_info(self, ns_ds):
        """Crear elemento KeyInfo con información del certificado"""
        key_info = etree.Element(f"{{{ns_ds}}}KeyInfo")
        
        # X509Data
        x509_data = etree.SubElement(key_info, f"{{{ns_ds}}}X509Data")
        
        # X509Certificate
        x509_cert = etree.SubElement(x509_data, f"{{{ns_ds}}}X509Certificate")
        
        # Obtener certificado en base64
        cert_der = self.certificate.public_bytes(Encoding.DER)
        cert_b64 = base64.b64encode(cert_der).decode('utf-8')
        x509_cert.text = cert_b64
        
        return key_info
    
    def _crear_object_xades(self, ns_ds, ns_xades):
        """Crear elemento Object con QualifyingProperties XAdES-BES"""
        obj = etree.Element(f"{{{ns_ds}}}Object")
        
        # QualifyingProperties
        qual_props = etree.SubElement(obj, f"{{{ns_xades}}}QualifyingProperties")
        qual_props.set("Target", "#signature")
        
        # SignedProperties
        signed_props = etree.SubElement(qual_props, f"{{{ns_xades}}}SignedProperties")
        signed_props.set("Id", "signed-properties")
        
        # SignedSignatureProperties
        signed_sig_props = etree.SubElement(signed_props, f"{{{ns_xades}}}SignedSignatureProperties")
        
        # SigningTime
        signing_time = etree.SubElement(signed_sig_props, f"{{{ns_xades}}}SigningTime")
        signing_time.text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # SigningCertificate
        signing_cert = etree.SubElement(signed_sig_props, f"{{{ns_xades}}}SigningCertificate")
        cert_element = etree.SubElement(signing_cert, f"{{{ns_xades}}}Cert")
        
        # CertDigest
        cert_digest = etree.SubElement(cert_element, f"{{{ns_xades}}}CertDigest")
        digest_method = etree.SubElement(cert_digest, f"{{{ns_ds}}}DigestMethod")
        digest_method.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha256")
        
        # Calcular hash del certificado
        cert_der = self.certificate.public_bytes(Encoding.DER)
        cert_hash = hashlib.sha256(cert_der).digest()
        cert_hash_b64 = base64.b64encode(cert_hash).decode('utf-8')
        
        digest_value = etree.SubElement(cert_digest, f"{{{ns_ds}}}DigestValue")
        digest_value.text = cert_hash_b64
        
        # IssuerSerial
        issuer_serial = etree.SubElement(cert_element, f"{{{ns_xades}}}IssuerSerial")
        
        x509_issuer = etree.SubElement(issuer_serial, f"{{{ns_ds}}}X509IssuerName")
        x509_issuer.text = self.certificate.issuer.rfc4514_string()
        
        x509_serial = etree.SubElement(issuer_serial, f"{{{ns_ds}}}X509SerialNumber")
        x509_serial.text = str(self.certificate.serial_number)
        
        return obj
    
    def _calcular_signature_value(self, doc, signed_info, signature_value_elem, ns_ds):
        """Calcular y establecer el SignatureValue real con padding PKCS#1 v1.5"""
        try:
            ns_xades = "http://uri.etsi.org/01903/v1.3.2#"
            
            # 1. Calcular digest del documento (sin signature)
            doc_copy = etree.fromstring(etree.tostring(doc))
            signature_elem = doc_copy.find(f".//{{{ns_ds}}}Signature")
            if signature_elem is not None:
                doc_copy.remove(signature_elem)
            
            doc_c14n = etree.tostring(
                doc_copy,
                method="c14n",
                exclusive=False,
                with_comments=False
            )
            
            doc_digest = hashlib.sha256(doc_c14n).digest()
            doc_digest_b64 = base64.b64encode(doc_digest).decode('utf-8')
            
            # 2. Calcular digest de SignedProperties
            signed_props = doc.find(f".//{{{ns_xades}}}SignedProperties")
            signed_props_digest_b64 = ""
            if signed_props is not None:
                signed_props_c14n = etree.tostring(
                    signed_props,
                    method="c14n",
                    exclusive=False,
                    with_comments=False
                )
                
                signed_props_digest = hashlib.sha256(signed_props_c14n).digest()
                signed_props_digest_b64 = base64.b64encode(signed_props_digest).decode('utf-8')
            
            # 3. Actualizar DigestValue del documento ANTES de firmar
            digest_value_elem = signed_info.find(f".//{{{ns_ds}}}Reference[@URI='']/{{{ns_ds}}}DigestValue")
            if digest_value_elem is not None:
                digest_value_elem.text = doc_digest_b64
            
            # 4. Actualizar DigestValue de SignedProperties ANTES de firmar
            props_digest_elem = signed_info.find(f".//{{{ns_ds}}}Reference[@URI='#signed-properties']/{{{ns_ds}}}DigestValue")
            if props_digest_elem is not None and signed_props_digest_b64:
                props_digest_elem.text = signed_props_digest_b64
            
            # 5. Recalcular SignedInfo con valores actualizados
            signed_info_c14n = etree.tostring(
                signed_info,
                method="c14n",
                exclusive=False,
                with_comments=False
            )
            
            # 6. Firmar SignedInfo con padding PKCS#1 v1.5
            from cryptography.hazmat.primitives.asymmetric import padding
            
            signature_bytes = self.private_key.sign(
                signed_info_c14n,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            
            signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
            signature_value_elem.text = signature_b64
            
        except Exception as e:
            raise XAdESError(f"Error al calcular SignatureValue: {e}")


def firmar_xml_xades_bes(xml_path, xml_firmado_path):
    """
    Función principal para firmar XML con XAdES-BES
    Compatible con la interfaz existente del sistema
    
    Args:
        xml_path (str): Ruta al XML sin firmar
        xml_firmado_path (str): Ruta donde guardar el XML firmado
    """
    try:
        firmador = SRIXAdESFirmador()
        return firmador.firmar_xml_xades_bes(xml_path, xml_firmado_path)
    except Exception as e:
        logger.error(f"Error en firma XAdES-BES: {e}")
        raise


# Función de fallback usando endesive (alternativa robusta)
def firmar_xml_con_endesive(xml_path, xml_firmado_path):
    """
    Firma XML usando endesive (librería especializada en XAdES)
    Fallback si la implementación manual falla
    """
    try:
        from endesive.xml import xades
        
        opciones = Opciones.objects.first()
        if not opciones or not opciones.firma_electronica or not opciones.password_firma:
            raise XAdESError('Firma electrónica o contraseña no configuradas')
        
        # Cargar certificado
        with open(opciones.firma_electronica.path, 'rb') as f:
            p12_data = f.read()
        
        # Usar endesive para firma XAdES-BES
        with open(xml_path, 'rb') as f:
            xml_data = f.read()
        
        # Configurar parámetros de firma
        datau = xml_data
        datas = {
            'certificate': opciones.firma_electronica.path,
            'password': opciones.password_firma,
        }
        
        # Firmar con XAdES-BES
        signature = xades.sign(datau, **datas)
        
        # Guardar resultado
        with open(xml_firmado_path, 'wb') as f:
            f.write(signature)
        
        logger.info(f"XML firmado con endesive XAdES-BES: {xml_firmado_path}")
        return True
        
    except ImportError:
        logger.error("endesive no está disponible para XAdES")
        raise XAdESError("Librería endesive no disponible")
    except Exception as e:
        logger.error(f"Error con endesive: {e}")
        raise XAdESError(f"Error en firma con endesive: {e}")
