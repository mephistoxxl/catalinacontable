"""
Firmador XAdES-BES replicando EXACTAMENTE la estructura del XML autorizado por el SRI.
Basado en el análisis del XML de producción autorizado de ALP SOLUCIONES.
"""

import base64
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree

from inventario.models import Empresa, Opciones
from inventario.utils.storage_io import storage_read_bytes, storage_write_bytes

logger = logging.getLogger(__name__)


class FirmadorXAdESError(Exception):
    """Error durante la firma XAdES-BES."""
    pass


def _canonicalizar_nodo(element: etree._Element) -> bytes:
    """
    Canonicaliza un elemento XML usando Inclusive C14N.
    Este es el método que usa el SRI.
    """
    return etree.tostring(
        element,
        method='c14n',
        exclusive=False,  # Inclusive C14N
        with_comments=False
    )


def _calcular_digest_sha1(data: bytes) -> str:
    """Calcula el digest SHA1 y lo retorna en base64."""
    return base64.b64encode(hashlib.sha1(data).digest()).decode('utf-8')


def _generar_id_unico() -> str:
    """Genera un ID numérico único de 6 dígitos."""
    return str(abs(hash(uuid.uuid4())) % 1000000)


def _obtener_modulo_exponente_rsa(certificate: x509.Certificate) -> Tuple[str, str]:
    """
    Extrae el módulo y exponente RSA del certificado.
    """
    public_key = certificate.public_key()
    public_numbers = public_key.public_numbers()
    
    # Módulo en base64
    modulo_bytes = public_numbers.n.to_bytes(
        (public_numbers.n.bit_length() + 7) // 8,
        byteorder='big'
    )
    modulo_b64 = base64.b64encode(modulo_bytes).decode('utf-8')
    
    # Exponente en base64
    exponente_bytes = public_numbers.e.to_bytes(
        (public_numbers.e.bit_length() + 7) // 8,
        byteorder='big'
    )
    exponente_b64 = base64.b64encode(exponente_bytes).decode('utf-8')
    
    return modulo_b64, exponente_b64


def _crear_estructura_xades(
    doc_tree: etree._ElementTree,
    certificate: x509.Certificate,
    certificate_der: bytes,
    signature_id: str
) -> Tuple[etree._Element, str, str, str]:
    """
    Crea la estructura completa de firma XAdES-BES replicando el XML autorizado.
    
    Returns:
        Tuple de (signature_element, signed_info_c14n, comprobante_id, keyinfo_id)
    """
    
    # Namespace maps
    DS_NS = "http://www.w3.org/2000/09/xmldsig#"
    ETSI_NS = "http://uri.etsi.org/01903/v1.3.2#"
    
    # Generar IDs únicos
    reference_id = f"Reference-ID-{_generar_id_unico()}"
    keyinfo_id = f"Certificate{_generar_id_unico()}"
    signed_props_id = f"Signature{signature_id}-SignedProperties{_generar_id_unico()}"
    signed_props_ref_id = f"SignedPropertiesID{_generar_id_unico()}"
    signature_value_id = f"SignatureValue{_generar_id_unico()}"
    object_id = f"Signature{signature_id}-Object{_generar_id_unico()}"
    
    # Obtener el elemento raíz
    # doc_tree ya es un Element (resultado de etree.fromstring)
    root = doc_tree
    comprobante_id = root.get('id', 'comprobante')
    
    # ==========================================
    # 1. CALCULAR DIGEST DEL COMPROBANTE
    # ==========================================
    comprobante_c14n = _canonicalizar_nodo(root)
    comprobante_digest = _calcular_digest_sha1(comprobante_c14n)
    
    # ==========================================
    # 2. CREAR ESTRUCTURA SignedInfo (SIN FIRMAR AÚN)
    # ==========================================
    signed_info = etree.Element(f'{{{DS_NS}}}SignedInfo')
    
    # CanonicalizationMethod
    canon_method = etree.SubElement(signed_info, f'{{{DS_NS}}}CanonicalizationMethod')
    canon_method.set('Algorithm', 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
    
    # SignatureMethod
    sig_method = etree.SubElement(signed_info, f'{{{DS_NS}}}SignatureMethod')
    sig_method.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#rsa-sha1')
    
    # Reference 1: Comprobante
    ref1 = etree.SubElement(signed_info, f'{{{DS_NS}}}Reference')
    ref1.set('Id', reference_id)
    ref1.set('URI', f'#{comprobante_id}')
    
    transforms1 = etree.SubElement(ref1, f'{{{DS_NS}}}Transforms')
    transform1 = etree.SubElement(transforms1, f'{{{DS_NS}}}Transform')
    transform1.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#enveloped-signature')
    
    digest_method1 = etree.SubElement(ref1, f'{{{DS_NS}}}DigestMethod')
    digest_method1.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
    
    digest_value1 = etree.SubElement(ref1, f'{{{DS_NS}}}DigestValue')
    digest_value1.text = comprobante_digest
    
    # ==========================================
    # 3. CREAR KeyInfo TEMPORALMENTE PARA CALCULAR SU DIGEST
    # ==========================================
    keyinfo_temp = etree.Element(f'{{{DS_NS}}}KeyInfo')
    keyinfo_temp.set('Id', keyinfo_id)
    
    x509data = etree.SubElement(keyinfo_temp, f'{{{DS_NS}}}X509Data')
    x509cert_elem = etree.SubElement(x509data, f'{{{DS_NS}}}X509Certificate')
    x509cert_elem.text = base64.b64encode(certificate_der).decode('utf-8')
    
    # Agregar KeyValue con RSA
    keyvalue = etree.SubElement(keyinfo_temp, f'{{{DS_NS}}}KeyValue')
    rsa_keyvalue = etree.SubElement(keyvalue, f'{{{DS_NS}}}RSAKeyValue')
    
    modulo_b64, exponente_b64 = _obtener_modulo_exponente_rsa(certificate)
    
    modulus_elem = etree.SubElement(rsa_keyvalue, f'{{{DS_NS}}}Modulus')
    modulus_elem.text = modulo_b64
    
    exponent_elem = etree.SubElement(rsa_keyvalue, f'{{{DS_NS}}}Exponent')
    exponent_elem.text = exponente_b64
    
    # Calcular digest del KeyInfo
    keyinfo_c14n = _canonicalizar_nodo(keyinfo_temp)
    keyinfo_digest = _calcular_digest_sha1(keyinfo_c14n)
    
    # Reference 2: KeyInfo (sin Transform)
    ref2 = etree.SubElement(signed_info, f'{{{DS_NS}}}Reference')
    ref2.set('URI', f'#{keyinfo_id}')
    
    digest_method2 = etree.SubElement(ref2, f'{{{DS_NS}}}DigestMethod')
    digest_method2.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
    
    digest_value2 = etree.SubElement(ref2, f'{{{DS_NS}}}DigestValue')
    digest_value2.text = keyinfo_digest
    
    # ==========================================
    # 4. CREAR SignedProperties TEMPORALMENTE PARA CALCULAR SU DIGEST
    # ==========================================
    
    # Obtener información del certificado
    cert_digest = _calcular_digest_sha1(certificate_der)
    issuer_name = certificate.issuer.rfc4514_string()
    serial_number = str(certificate.serial_number)
    
    # Timestamp actual
    timestamp = datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')
    # Formatear timezone correctamente (ej: -05:00)
    if len(timestamp) > 5:
        timestamp = timestamp[:-2] + ':' + timestamp[-2:]
    
    signed_props = etree.Element(f'{{{ETSI_NS}}}SignedProperties')
    signed_props.set('Id', signed_props_id)
    
    signed_sig_props = etree.SubElement(signed_props, f'{{{ETSI_NS}}}SignedSignatureProperties')
    
    # SigningTime
    signing_time = etree.SubElement(signed_sig_props, f'{{{ETSI_NS}}}SigningTime')
    signing_time.text = timestamp
    
    # SigningCertificate
    signing_cert = etree.SubElement(signed_sig_props, f'{{{ETSI_NS}}}SigningCertificate')
    cert_elem = etree.SubElement(signing_cert, f'{{{ETSI_NS}}}Cert')
    
    cert_digest_elem = etree.SubElement(cert_elem, f'{{{ETSI_NS}}}CertDigest')
    digest_method_cert = etree.SubElement(cert_digest_elem, f'{{{DS_NS}}}DigestMethod')
    digest_method_cert.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
    digest_value_cert = etree.SubElement(cert_digest_elem, f'{{{DS_NS}}}DigestValue')
    digest_value_cert.text = cert_digest
    
    issuer_serial = etree.SubElement(cert_elem, f'{{{ETSI_NS}}}IssuerSerial')
    issuer_name_elem = etree.SubElement(issuer_serial, f'{{{DS_NS}}}X509IssuerName')
    issuer_name_elem.text = issuer_name
    serial_number_elem = etree.SubElement(issuer_serial, f'{{{DS_NS}}}X509SerialNumber')
    serial_number_elem.text = serial_number
    
    # SignedDataObjectProperties
    signed_data_props = etree.SubElement(signed_props, f'{{{ETSI_NS}}}SignedDataObjectProperties')
    data_obj_format = etree.SubElement(signed_data_props, f'{{{ETSI_NS}}}DataObjectFormat')
    data_obj_format.set('ObjectReference', f'#{reference_id}')
    
    description = etree.SubElement(data_obj_format, f'{{{ETSI_NS}}}Description')
    description.text = 'contenido comprobante'
    
    mime_type = etree.SubElement(data_obj_format, f'{{{ETSI_NS}}}MimeType')
    mime_type.text = 'text/xml'
    
    # Calcular digest de SignedProperties
    signed_props_c14n = _canonicalizar_nodo(signed_props)
    signed_props_digest = _calcular_digest_sha1(signed_props_c14n)
    
    # Reference 3: SignedProperties
    ref3 = etree.SubElement(signed_info, f'{{{DS_NS}}}Reference')
    ref3.set('Id', signed_props_ref_id)
    ref3.set('Type', 'http://uri.etsi.org/01903#SignedProperties')
    ref3.set('URI', f'#{signed_props_id}')
    
    digest_method3 = etree.SubElement(ref3, f'{{{DS_NS}}}DigestMethod')
    digest_method3.set('Algorithm', 'http://www.w3.org/2000/09/xmldsig#sha1')
    
    digest_value3 = etree.SubElement(ref3, f'{{{DS_NS}}}DigestValue')
    digest_value3.text = signed_props_digest
    
    # ==========================================
    # 5. CREAR ESTRUCTURA SIGNATURE COMPLETA PRIMERO
    # ==========================================
    # CRÍTICO: Solo xmlns:ds en Signature root
    # xmlns:etsi SOLO se declara donde se usa (en QualifyingProperties)
    # Si se pone aquí, se hereda a SignedInfo y cambia el C14N (+47 bytes)
    nsmap = {
        'ds': DS_NS
    }
    
    signature = etree.Element(f'{{{DS_NS}}}Signature', nsmap=nsmap)
    signature.set('Id', f'Signature{signature_id}')
    
    # Agregar SignedInfo
    signature.append(signed_info)
    
    # SignatureValue (se llenará después con la firma)
    sig_value = etree.SubElement(signature, f'{{{DS_NS}}}SignatureValue')
    sig_value.set('Id', signature_value_id)
    
    # KeyInfo
    signature.append(keyinfo_temp)
    
    # Object con QualifyingProperties
    obj = etree.SubElement(signature, f'{{{DS_NS}}}Object')
    obj.set('Id', object_id)
    
    # Declarar xmlns:etsi AQUÍ, no en Signature (evita herencia a SignedInfo)
    qualifying_props = etree.SubElement(obj, f'{{{ETSI_NS}}}QualifyingProperties', nsmap={'etsi': ETSI_NS})
    qualifying_props.set('Target', f'#Signature{signature_id}')
    
    qualifying_props.append(signed_props)
    
    # ==========================================
    # 6. AHORA CANONICALIZAR SignedInfo (CON namespaces heredados)
    # ==========================================
    signed_info_c14n = _canonicalizar_nodo(signed_info)
    
    return signature, signed_info_c14n, sig_value


def firmar_xml_xades_bes_sri(
    xml_path: str,
    xml_firmado_path: str,
    *,
    empresa: Optional[Empresa] = None,
    opciones: Optional[Opciones] = None,
) -> bool:
    """
    Firma un XML con XAdES-BES replicando EXACTAMENTE la estructura del SRI.
    Basado en XML autorizado de producción.
    """
    
    logger.info("🔥 Iniciando firma XAdES-BES (estructura SRI)")
    
    # ==========================================
    # 1. OBTENER CONFIGURACIÓN
    # ==========================================
    if opciones is None:
        if empresa:
            try:
                opciones = Opciones.objects.get(empresa=empresa)
            except Opciones.DoesNotExist:
                raise FirmadorXAdESError(f"No se encontró configuración de firma para empresa {empresa}")
        else:
            # Intentar obtener la primera configuración disponible
            opciones = Opciones.objects.first()
            if not opciones:
                raise FirmadorXAdESError("No se encontró ninguna configuración de firma")
    
    # ==========================================
    # 2. CARGAR XML
    # ==========================================
    try:
        xml_bytes = storage_read_bytes(xml_path)
        doc_tree = etree.fromstring(xml_bytes)
    except Exception as e:
        raise FirmadorXAdESError(f"Error al leer XML: {e}")
    
    # ==========================================
    # 3. CARGAR CERTIFICADO P12
    # ==========================================
    try:
        with opciones.firma_electronica.open('rb') as f:
            p12_bytes = f.read()
        
        private_key, certificate, _ = pkcs12.load_key_and_certificates(
            p12_bytes,
            (opciones.password_firma or "").encode('utf-8')
        )
        
        if not private_key or not certificate:
            raise FirmadorXAdESError("Certificado inválido")
        
        certificate_der = certificate.public_bytes(serialization.Encoding.DER)
        
    except Exception as e:
        raise FirmadorXAdESError(f"Error al cargar certificado: {e}")
    
    logger.info(f"   Certificado: {certificate.subject.rfc4514_string()}")
    
    # ==========================================
    # 4. CREAR ESTRUCTURA XADES
    # ==========================================
    signature_id = _generar_id_unico()
    
    try:
        signature, signed_info_c14n, sig_value_elem = _crear_estructura_xades(
            doc_tree,
            certificate,
            certificate_der,
            signature_id
        )
    except Exception as e:
        raise FirmadorXAdESError(f"Error al crear estructura XAdES: {e}")
    
    logger.info(f"   SignedInfo canonicalizado: {len(signed_info_c14n)} bytes")
    logger.info(f"   Digest SHA1: {_calcular_digest_sha1(signed_info_c14n)}")
    
    # ==========================================
    # 5. FIRMAR SignedInfo con RSA-SHA1
    # ==========================================
    try:
        signature_bytes = private_key.sign(
            signed_info_c14n,
            padding.PKCS1v15(),
            hashes.SHA1()
        )
        signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
        sig_value_elem.text = signature_b64
        
    except Exception as e:
        raise FirmadorXAdESError(f"Error al firmar: {e}")
    
    logger.info(f"   Firma RSA-SHA1: {len(signature_bytes)} bytes")
    
    # ==========================================
    # 6. INSERTAR SIGNATURE EN EL XML
    # ==========================================
    if isinstance(doc_tree, etree._Element):
        root = doc_tree
    else:
        root = doc_tree.getroot()
    
    root.append(signature)
    
    # ==========================================
    # 7. SERIALIZAR Y GUARDAR
    # ==========================================
    try:
        xml_firmado = etree.tostring(
            root,
            xml_declaration=True,
            encoding='utf-8',
            standalone=True
        )
        
        storage_write_bytes(xml_firmado_path, xml_firmado)
        
    except Exception as e:
        raise FirmadorXAdESError(f"Error al guardar XML firmado: {e}")
    
    logger.info(f"✅ XML firmado exitosamente")
    logger.info(f"   Guardado en: {xml_firmado_path}")
    
    return True
