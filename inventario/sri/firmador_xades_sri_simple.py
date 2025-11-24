"""
Firmador XAdES-BES simplificado para SRI Ecuador
Genera firma digital compatible con los requisitos del SRI sin elementos extra
"""
import logging
import hashlib
import base64
import uuid
from datetime import datetime
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography import x509

logger = logging.getLogger(__name__)


class FirmadorXAdESSRIEcuador:
    """
    Firmador XAdES-BES simplificado específico para SRI Ecuador
    Genera solo los elementos requeridos sin extras de Certum/Polonia
    """
    
    def __init__(self, p12_bytes, password):
        """
        Inicializa el firmador con certificado PKCS#12
        
        Args:
            p12_bytes: Contenido del archivo .p12/.pfx
            password: Contraseña del certificado
        """
        self.p12_bytes = p12_bytes
        self.password = password
        self._cargar_certificado()
    
    def _cargar_certificado(self):
        """Carga el certificado y clave privada desde PKCS#12"""
        try:
            self.private_key, self.certificate, additional_certs = pkcs12.load_key_and_certificates(
                self.p12_bytes,
                self.password.encode() if isinstance(self.password, str) else self.password
            )
            
            if not self.private_key or not self.certificate:
                raise ValueError("No se pudo extraer la llave privada o el certificado del archivo .p12")
            
            logger.info("Certificado cargado exitosamente")
            
        except Exception as e:
            logger.error(f"Error cargando certificado PKCS#12: {e}")
            raise ValueError(f"Certificado inválido o contraseña incorrecta: {e}")
    
    def firmar_xml(self, xml_string):
        """
        Firma un XML con XAdES-BES simplificado para SRI
        
        Args:
            xml_string: XML sin firmar como string
            
        Returns:
            str: XML firmado
        """
        try:
            # Parsear XML
            root = etree.fromstring(xml_string.encode('utf-8'))
            
            # Asegurar que el elemento raíz tenga Id="comprobante"
            if not root.get('id') and not root.get('Id'):
                root.set('id', 'comprobante')
                root.set('Id', 'comprobante')
            
            # Generar IDs únicos para los elementos de firma
            signature_id = f"Signature_{uuid.uuid4().hex[:8]}"
            signed_properties_id = f"SignedProperties_{uuid.uuid4().hex[:8]}"
            
            # Crear elemento Signature
            ds_ns = "http://www.w3.org/2000/09/xmldsig#"
            xades_ns = "http://uri.etsi.org/01903/v1.3.2#"
            
            NSMAP = {
                'ds': ds_ns,
                'xades': xades_ns
            }
            
            signature = etree.Element(
                f"{{{ds_ns}}}Signature",
                nsmap=NSMAP,
                Id=signature_id
            )
            
            # 1. SignedInfo (con placeholders)
            signed_info = self._crear_signed_info(ds_ns, signed_properties_id)
            signature.append(signed_info)
            
            # 2. SignatureValue (se calculará después)
            signature_value = etree.SubElement(signature, f"{{{ds_ns}}}SignatureValue")
            signature_value.set('Id', f"SignatureValue_{uuid.uuid4().hex[:8]}")
            
            # 3. KeyInfo
            key_info = self._crear_key_info(ds_ns)
            signature.append(key_info)
            
            # 4. Object con QualifyingProperties
            obj = self._crear_qualifying_properties(ds_ns, xades_ns, signature_id, signed_properties_id)
            signature.append(obj)
            
            # Agregar firma al documento
            root.append(signature)
            
            # CALCULAR DIGEST VALUES
            # Digest del documento (con enveloped-signature transform)
            root_copy = etree.fromstring(etree.tostring(root))
            # Remover la firma para calcular el digest
            for sig in root_copy.findall(f".//{{{ds_ns}}}Signature"):
                sig.getparent().remove(sig)
            
            doc_c14n = etree.tostring(root_copy, method='c14n', exclusive=False, with_comments=False)
            doc_digest = hashlib.sha1(doc_c14n).digest()
            doc_digest_b64 = base64.b64encode(doc_digest).decode('ascii')
            
            # Actualizar digest del documento
            ref1 = signed_info.find(f".//{{{ds_ns}}}Reference[@URI='#comprobante']", namespaces={'ds': ds_ns})
            if ref1 is not None:
                digest_val1 = ref1.find(f"{{{ds_ns}}}DigestValue")
                if digest_val1 is not None:
                    digest_val1.text = doc_digest_b64
            
            # Digest de SignedProperties
            signed_props_elem = signature.find(
                f".//{{{xades_ns}}}SignedProperties[@Id='{signed_properties_id}']",
                namespaces={'xades': xades_ns}
            )
            
            if signed_props_elem is not None:
                props_c14n = etree.tostring(signed_props_elem, method='c14n', exclusive=False, with_comments=False)
                props_digest = hashlib.sha1(props_c14n).digest()
                props_digest_b64 = base64.b64encode(props_digest).decode('ascii')
                
                # Actualizar digest de SignedProperties
                ref2 = signed_info.find(
                    f".//{{{ds_ns}}}Reference[@URI='#{signed_properties_id}']",
                    namespaces={'ds': ds_ns}
                )
                if ref2 is not None:
                    digest_val2 = ref2.find(f"{{{ds_ns}}}DigestValue")
                    if digest_val2 is not None:
                        digest_val2.text = props_digest_b64
            
            # Calcular y agregar SignatureValue
            signature_value_bytes = self._calcular_signature_value(signed_info, ds_ns)
            signature_value.text = "\n" + signature_value_bytes + "\n"
            
            # Convertir a string
            xml_firmado = etree.tostring(
                root,
                pretty_print=True,
                xml_declaration=True,
                encoding='UTF-8'
            ).decode('utf-8')
            
            logger.info("✅ XML firmado exitosamente con XAdES-BES SRI Ecuador")
            return xml_firmado
            
        except Exception as e:
            logger.error(f"Error firmando XML: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _crear_signed_info(self, ds_ns, signed_properties_id):
        """Crea el elemento SignedInfo"""
        signed_info = etree.Element(f"{{{ds_ns}}}SignedInfo")
        
        # CanonicalizationMethod
        c14n_method = etree.SubElement(signed_info, f"{{{ds_ns}}}CanonicalizationMethod")
        c14n_method.set('Algorithm', 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
        
        # SignatureMethod
        sig_method = etree.SubElement(signed_info, f"{{{ds_ns}}}SignatureMethod")
        sig_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#rsa-sha1')
        
        # Reference al documento
        ref1 = etree.SubElement(signed_info, f"{{{ds_ns}}}Reference")
        ref1.set('URI', '#comprobante')
        
        transforms1 = etree.SubElement(ref1, f"{{{ds_ns}}}Transforms")
        transform1a = etree.SubElement(transforms1, f"{{{ds_ns}}}Transform")
        transform1a.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#enveloped-signature')
        
        digest_method1 = etree.SubElement(ref1, f"{{{ds_ns}}}DigestMethod")
        digest_method1.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
        
        digest_value1 = etree.SubElement(ref1, f"{{{ds_ns}}}DigestValue")
        digest_value1.text = "PLACEHOLDER1"  # Se calculará después
        
        # Reference a SignedProperties
        ref2 = etree.SubElement(signed_info, f"{{{ds_ns}}}Reference")
        ref2.set('Type', 'http://uri.etsi.org/01903#SignedProperties')
        ref2.set('URI', f'#{signed_properties_id}')
        
        digest_method2 = etree.SubElement(ref2, f"{{{ds_ns}}}DigestMethod")
        digest_method2.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
        
        digest_value2 = etree.SubElement(ref2, f"{{{ds_ns}}}DigestValue")
        digest_value2.text = "PLACEHOLDER2"  # Se calculará después
        
        return signed_info
    
    def _crear_key_info(self, ds_ns):
        """Crea el elemento KeyInfo con el certificado"""
        key_info = etree.Element(f"{{{ds_ns}}}KeyInfo")
        
        # X509Data
        x509_data = etree.SubElement(key_info, f"{{{ds_ns}}}X509Data")
        x509_cert = etree.SubElement(x509_data, f"{{{ds_ns}}}X509Certificate")
        
        # Certificado en base64
        cert_der = self.certificate.public_bytes(Encoding.DER)
        cert_b64 = base64.b64encode(cert_der).decode('ascii')
        x509_cert.text = "\n" + cert_b64 + "\n"
        
        # KeyValue (opcional pero recomendado)
        key_value = etree.SubElement(key_info, f"{{{ds_ns}}}KeyValue")
        rsa_key_value = etree.SubElement(key_value, f"{{{ds_ns}}}RSAKeyValue")
        
        # Obtener módulo y exponente (simplificado)
        public_key = self.certificate.public_key()
        public_numbers = public_key.public_numbers()
        
        modulus = etree.SubElement(rsa_key_value, f"{{{ds_ns}}}Modulus")
        modulus.text = base64.b64encode(public_numbers.n.to_bytes(
            (public_numbers.n.bit_length() + 7) // 8, 'big'
        )).decode('ascii')
        
        exponent = etree.SubElement(rsa_key_value, f"{{{ds_ns}}}Exponent")
        exponent.text = base64.b64encode(public_numbers.e.to_bytes(
            (public_numbers.e.bit_length() + 7) // 8, 'big'
        )).decode('ascii')
        
        return key_info
    
    def _crear_qualifying_properties(self, ds_ns, xades_ns, signature_id, signed_properties_id):
        """Crea el Object con QualifyingProperties simplificado para SRI"""
        obj = etree.Element(f"{{{ds_ns}}}Object")
        
        qualifying_props = etree.SubElement(obj, f"{{{xades_ns}}}QualifyingProperties")
        qualifying_props.set('Target', f'#{signature_id}')
        
        signed_props = etree.SubElement(qualifying_props, f"{{{xades_ns}}}SignedProperties")
        signed_props.set('Id', signed_properties_id)
        
        # SignedSignatureProperties
        signed_sig_props = etree.SubElement(signed_props, f"{{{xades_ns}}}SignedSignatureProperties")
        
        # SigningTime
        signing_time = etree.SubElement(signed_sig_props, f"{{{xades_ns}}}SigningTime")
        # Usar hora de Ecuador (UTC-5) correctamente
        from datetime import datetime, timezone, timedelta
        ecuador_tz = timezone(timedelta(hours=-5))
        now_ecuador = datetime.now(ecuador_tz)
        signing_time.text = now_ecuador.strftime('%Y-%m-%dT%H:%M:%S%z')
        # Formatear timezone como -05:00 en lugar de -0500
        if signing_time.text.endswith('+0000') or signing_time.text.endswith('-0500'):
            signing_time.text = signing_time.text[:-2] + ':' + signing_time.text[-2:]
        
        # SigningCertificate
        signing_cert = etree.SubElement(signed_sig_props, f"{{{xades_ns}}}SigningCertificate")
        cert_elem = etree.SubElement(signing_cert, f"{{{xades_ns}}}Cert")
        cert_digest = etree.SubElement(cert_elem, f"{{{xades_ns}}}CertDigest")
        
        digest_method = etree.SubElement(cert_digest, f"{{{ds_ns}}}DigestMethod")
        digest_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
        
        digest_value = etree.SubElement(cert_digest, f"{{{ds_ns}}}DigestValue")
        cert_der = self.certificate.public_bytes(Encoding.DER)
        cert_hash = hashlib.sha1(cert_der).digest()
        digest_value.text = base64.b64encode(cert_hash).decode('ascii')
        
        # IssuerSerial
        issuer_serial = etree.SubElement(cert_elem, f"{{{xades_ns}}}IssuerSerial")
        x509_issuer = etree.SubElement(issuer_serial, f"{{{ds_ns}}}X509IssuerName")
        x509_issuer.text = self.certificate.issuer.rfc4514_string()
        
        x509_serial = etree.SubElement(issuer_serial, f"{{{ds_ns}}}X509SerialNumber")
        x509_serial.text = str(self.certificate.serial_number)
        
        # SignedDataObjectProperties - SIMPLIFICADO SIN CERTUM
        signed_data_props = etree.SubElement(signed_props, f"{{{xades_ns}}}SignedDataObjectProperties")
        data_obj_format = etree.SubElement(signed_data_props, f"{{{xades_ns}}}DataObjectFormat")
        data_obj_format.set('ObjectReference', '#comprobante')
        
        # MimeType simple
        mime_type = etree.SubElement(data_obj_format, f"{{{xades_ns}}}MimeType")
        mime_type.text = 'text/xml'
        
        return obj
    
    def _calcular_signature_value(self, signed_info, ds_ns):
        """Calcula el SignatureValue"""
        # Canonizar SignedInfo
        c14n_xml = etree.tostring(
            signed_info,
            method='c14n',
            exclusive=False,
            with_comments=False
        )
        
        # Firmar con la clave privada
        signature_bytes = self.private_key.sign(
            c14n_xml,
            padding.PKCS1v15(),
            hashes.SHA1()
        )
        
        # Convertir a base64
        signature_b64 = base64.b64encode(signature_bytes).decode('ascii')
        
        return signature_b64
