#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firmador XAdES-BES para SRI Ecuador
Basado en xades-bes-sri-ec - Implementación probada en producción
Adaptado para usar lxml y Django storage
"""

import logging
import base64
import hashlib
import re
import codecs
import math
from random import random
from datetime import datetime
from lxml import etree
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from cryptography.x509.extensions import KeyUsage
import os

logger = logging.getLogger(__name__)

try:
    from OpenSSL import crypto
except ImportError:
    crypto = None
    logger.warning("⚠️  OpenSSL no disponible, usando solo cryptography")

# Constantes
MAX_LINE_SIZE = 76
XMLNS = 'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:etsi="http://uri.etsi.org/01903/v1.3.2#"'

# Importar storage
STORAGE_AVAILABLE = False

def storage_read_bytes(path):
    """Leer archivo (compatibilidad con y sin Django)"""
    if os.path.exists(path):
        with open(path, 'rb') as f:
            return f.read()
    else:
        # Intentar con Django storage como fallback
        try:
            from inventario.utils.storage_io import storage_read_bytes as django_read
            return django_read(path)
        except:
            raise FileNotFoundError(f"No se encontró: {path}")


def storage_write_bytes(path, data):
    """Escribir archivo (compatibilidad con y sin Django)"""
    try:
        # Intentar primero con Django storage
        from inventario.utils.storage_io import storage_write_bytes as django_write
        django_write(path, data)
        logger.debug(f"Guardado con Django storage: {path}")
    except:
        # Fallback: archivo local
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data if isinstance(data, bytes) else data.encode())
        logger.debug(f"Guardado como archivo local: {path}")


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def p_obtener_aleatorio():
    """Genera número aleatorio como el SRI"""
    return int(math.floor(random() * 999000) + 990)


def split_string_every_n(cad, n):
    """Divide una cadena cada n caracteres con saltos de línea"""
    res = [cad[i:i + n] for i in range(0, len(cad), n)]
    return '\n'.join(res)


def encode_base64(data, encoding='UTF-8'):
    """Codifica en base64"""
    if isinstance(data, str):
        data = data.encode(encoding)
    b64 = base64.b64encode(data).decode(encoding)
    return b64


def sha1_base64(data):
    """Calcula SHA1 y codifica en base64"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    sha1_hash = hashlib.sha1(data).digest()
    return encode_base64(sha1_hash)


def format_xml_string(cad):
    """Formatea XML eliminando espacios innecesarios"""
    cad = cad.replace('\n', '')
    cad = re.sub(' +', ' ', cad).replace('> ', '>').replace(' <', '<')
    return cad


def get_c14n(xml_string):
    """
    Canonicalización C14N usando lxml
    (Reemplaza xmllint --c14n)
    """
    try:
        # Parsear el XML
        if isinstance(xml_string, str):
            doc = etree.fromstring(xml_string.encode('utf-8'))
        else:
            doc = etree.fromstring(xml_string)
        
        # Aplicar C14N (Inclusive, sin comentarios)
        c14n_bytes = etree.tostring(
            doc,
            method='c14n',
            exclusive=False,  # Inclusive C14N
            with_comments=False
        )
        
        return c14n_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Error en C14N: {e}")
        raise


def get_xml_nodo_final(xml_element_tree):
    """Obtiene el tag final del XML"""
    return '</{}>'.format(xml_element_tree.getroot().tag)


# ============================================================================
# FUNCIONES PARA CERTIFICADO
# ============================================================================

def get_certificados_validos(archivo_bytes, password):
    """Obtiene certificados válidos del archivo P12"""
    fecha_hora_actual = datetime.now()
    
    # Asegurar que password sea bytes
    if isinstance(password, str):
        password = password.encode('utf-8')
    
    try:
        # Intentar con la nueva API de cryptography 46+
        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            archivo_bytes, 
            password
        )
    except TypeError:
        # Fallback para versiones anteriores
        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            archivo_bytes, 
            password,
            backend=default_backend()
        )
    
    certificados_no_caducados = []
    certificados_validos = []
    
    if certificate and certificate.not_valid_after_utc > fecha_hora_actual.replace(tzinfo=None):
        certificados_no_caducados.append(certificate)
    
    if additional_certificates:
        for cert in additional_certificates:
            if cert.not_valid_after_utc > fecha_hora_actual.replace(tzinfo=None):
                certificados_no_caducados.append(cert)
    
    # Filtrar certificados con digital_signature
    for cert in certificados_no_caducados:
        try:
            for ext in cert.extensions:
                if type(ext.value) == KeyUsage:
                    if ext.value.digital_signature:
                        certificados_validos.append(cert)
                        break
        except:
            # Si no tiene extensiones o falla, incluirlo de todas formas
            certificados_validos.append(cert)
    
    return certificados_validos, private_key


def get_exponente(exp_int):
    """Convierte exponente RSA a base64"""
    exponent = '{:X}'.format(exp_int)
    exponent = exponent.zfill(6)
    exponent = codecs.encode(codecs.decode(exponent, 'HEX'), 'BASE64').decode()
    return exponent.strip()


def get_modulo(mod_int):
    """Convierte módulo RSA a base64 multi-línea"""
    modulo = '{:X}'.format(mod_int)
    
    # Dividir cada 2 caracteres
    modulo_parts = re.findall(r'(\w{2})', modulo)
    modulo_bytes = bytes([int(x, 16) for x in modulo_parts])
    modulo_b64 = encode_base64(modulo_bytes)
    
    # Dividir en líneas de MAX_LINE_SIZE
    return split_string_every_n(modulo_b64, MAX_LINE_SIZE)


def get_certificate_x509(cert_pem):
    """Extrae certificado X509 en base64"""
    cert_str = cert_pem.decode() if isinstance(cert_pem, bytes) else str(cert_pem)
    
    cert_match = re.findall(
        r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----",
        cert_str, flags=re.DOTALL
    )
    
    if not cert_match:
        raise ValueError("No se pudo extraer certificado X509")
    
    cert_x509 = cert_match[0].replace('\n', '').replace('\\n', '')
    return split_string_every_n(cert_x509, MAX_LINE_SIZE)


# ============================================================================
# PLANTILLAS XML
# ============================================================================

def get_signed_properties(signature_number, signed_properties_number, 
                          certificate_hash, serial_number, reference_id_number, 
                          issuer_name):
    """Genera SignedProperties"""
    # Usar timezone de Ecuador (-05:00)
    fecha_hora = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-05:00")
    
    template = """
    <etsi:SignedProperties Id="Signature%(signature_number)s-SignedProperties%(signed_properties_number)s">
        <etsi:SignedSignatureProperties>
            <etsi:SigningTime>%(fecha_hora)s</etsi:SigningTime>
            <etsi:SigningCertificate>
                <etsi:Cert>
                    <etsi:CertDigest>
                        <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
                        <ds:DigestValue>%(certificate_hash)s</ds:DigestValue>
                    </etsi:CertDigest>
                    <etsi:IssuerSerial>
                        <ds:X509IssuerName>%(issuer_name)s</ds:X509IssuerName>
                        <ds:X509SerialNumber>%(serial_number)s</ds:X509SerialNumber>
                    </etsi:IssuerSerial>
                </etsi:Cert>
            </etsi:SigningCertificate>
        </etsi:SignedSignatureProperties>
        <etsi:SignedDataObjectProperties>
            <etsi:DataObjectFormat ObjectReference="#Reference-ID-%(reference_id_number)s">
                <etsi:Description>contenido comprobante</etsi:Description>
                <etsi:MimeType>text/xml</etsi:MimeType>
            </etsi:DataObjectFormat>
        </etsi:SignedDataObjectProperties>
    </etsi:SignedProperties>"""
    
    signed_properties = template % {
        'signature_number': signature_number,
        'signed_properties_number': signed_properties_number,
        'certificate_hash': certificate_hash,
        'serial_number': serial_number,
        'reference_id_number': reference_id_number,
        'fecha_hora': fecha_hora,
        'issuer_name': issuer_name
    }
    
    return format_xml_string(signed_properties)


def get_key_info(certificate_number, certificate_x509, modulus, exponent):
    """Genera KeyInfo con X509 y KeyValue"""
    template = """<ds:KeyInfo Id="Certificate%(certificate_number)s">
<ds:X509Data>
<ds:X509Certificate>
%(certificate_x509)s
</ds:X509Certificate>
</ds:X509Data>
<ds:KeyValue>
<ds:RSAKeyValue>
<ds:Modulus>
%(modulus)s
</ds:Modulus>
<ds:Exponent>%(exponent)s</ds:Exponent>
</ds:RSAKeyValue>
</ds:KeyValue>
</ds:KeyInfo>"""
    
    return template % {
        'certificate_number': certificate_number,
        'certificate_x509': certificate_x509,
        'modulus': modulus,
        'exponent': exponent
    }


def get_signed_info(signed_info_number, signed_properties_id_number, 
                    sha1_signed_properties, certificate_number, sha1_certificate,
                    reference_id_number, sha1_comprobante, signature_number, 
                    signed_properties_number):
    """Genera SignedInfo con 3 referencias"""
    template = """<ds:SignedInfo Id="Signature-SignedInfo%(signed_info_number)s">
<ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
<ds:SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
<ds:Reference Id="SignedPropertiesID%(signed_properties_id_number)s" Type="http://uri.etsi.org/01903#SignedProperties" URI="#Signature%(signature_number)s-SignedProperties%(signed_properties_number)s">
<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
<ds:DigestValue>%(sha1_signed_properties)s</ds:DigestValue>
</ds:Reference>
<ds:Reference URI="#Certificate%(certificate_number)s">
<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
<ds:DigestValue>%(sha1_certificate)s</ds:DigestValue>
</ds:Reference>
<ds:Reference Id="Reference-ID-%(reference_id_number)s" URI="#comprobante">
<ds:Transforms>
<ds:Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
</ds:Transforms>
<ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
<ds:DigestValue>%(sha1_comprobante)s</ds:DigestValue>
</ds:Reference>
</ds:SignedInfo>"""
    
    return template % {
        'signed_info_number': signed_info_number,
        'signed_properties_id_number': signed_properties_id_number,
        'sha1_signed_properties': sha1_signed_properties,
        'certificate_number': certificate_number,
        'sha1_certificate': sha1_certificate,
        'reference_id_number': reference_id_number,
        'sha1_comprobante': sha1_comprobante,
        'signature_number': signature_number,
        'signed_properties_number': signed_properties_number
    }


def get_xades_bes(xmls, signature_number, signature_value_number, object_number,
                  signed_info, signature, key_info, signed_properties):
    """Genera estructura XAdES-BES completa"""
    template = """<ds:Signature %(xmls)s Id="Signature%(signature_number)s">
%(signed_info)s
<ds:SignatureValue Id="SignatureValue%(signature_value_number)s">
%(signature)s
</ds:SignatureValue>
%(key_info)s
<ds:Object Id="Signature%(signature_number)s-Object%(object_number)s"><etsi:QualifyingProperties Target="#Signature%(signature_number)s">%(signed_properties)s</etsi:QualifyingProperties></ds:Object></ds:Signature>"""
    
    return template % {
        'xmls': xmls,
        'signature_number': signature_number,
        'signature_value_number': signature_value_number,
        'object_number': object_number,
        'signed_info': signed_info,
        'signature': signature,
        'key_info': key_info,
        'signed_properties': signed_properties
    }


# ============================================================================
# FUNCIÓN PRINCIPAL DE FIRMA
# ============================================================================

def firmar_xml_xades_bes(xml_path, cert_path, password, xml_firmado_path):
    """
    Firma un XML con XAdES-BES según especificación SRI Ecuador
    
    Args:
        xml_path: Ruta al XML sin firmar
        cert_path: Ruta al certificado P12
        password: Contraseña del certificado
        xml_firmado_path: Ruta donde guardar XML firmado
    
    Returns:
        bool: True si firma exitosa
    """
    try:
        logger.info("=" * 80)
        logger.info("INICIANDO FIRMA XADES-BES (xades-bes-sri-ec)")
        logger.info("=" * 80)
        
        # Leer archivos
        logger.info(f"📄 Leyendo XML: {xml_path}")
        xml_content = storage_read_bytes(xml_path)
        if isinstance(xml_content, bytes):
            xml_content = xml_content.decode('utf-8')
        
        logger.info(f"🔐 Leyendo certificado: {cert_path}")
        cert_bytes = storage_read_bytes(cert_path)
        
        # Obtener certificados válidos
        certificados, private_key = get_certificados_validos(cert_bytes, password)
        
        if not certificados:
            raise Exception("No se encontraron certificados válidos")
        
        cert = certificados[0]
        logger.info(f"✅ Certificado válido encontrado")
        
        # Convertir certificado a PEM con OpenSSL
        cert_pem = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
        certificate_x509 = get_certificate_x509(cert_pem)
        
        # Calcular hash del certificado DER
        cert_pem_obj = crypto.load_certificate(crypto.FILETYPE_PEM, cert_pem)
        cert_der = crypto.dump_certificate(crypto.FILETYPE_ASN1, cert_pem_obj)
        certificate_hash = sha1_base64(cert_der)
        
        # Extraer módulo y exponente RSA
        modulo = get_modulo(cert.public_key().public_numbers().n)
        exponente = get_exponente(cert.public_key().public_numbers().e)
        
        # Datos del certificado
        serial_number = cert_pem_obj.get_serial_number()
        issuer = cert_pem_obj.get_issuer()
        issuer_name = "".join(
            ",{0:s}={1:s}".format(name.decode(), value.decode()) 
            for name, value in issuer.get_components()
        )
        issuer_name = issuer_name[1:] if issuer_name.startswith(',') else issuer_name
        
        logger.info(f"📋 Serial: {serial_number}")
        logger.info(f"📋 Issuer: {issuer_name}")
        
        # Parsear XML original
        xml_tree = etree.ElementTree(etree.fromstring(xml_content.encode('utf-8')))
        xml_c14n = get_c14n(xml_content)
        
        # Calcular digest del comprobante
        sha1_comprobante = sha1_base64(xml_c14n.encode('utf-8'))
        logger.info(f"🔐 SHA1 Comprobante: {sha1_comprobante}")
        
        # Generar IDs aleatorios
        certificate_number = p_obtener_aleatorio()
        signature_number = p_obtener_aleatorio()
        signed_properties_number = p_obtener_aleatorio()
        signed_info_number = p_obtener_aleatorio()
        signed_properties_id_number = p_obtener_aleatorio()
        reference_id_number = p_obtener_aleatorio()
        signature_value_number = p_obtener_aleatorio()
        object_number = p_obtener_aleatorio()
        
        # 1. Generar SignedProperties
        signed_properties = get_signed_properties(
            signature_number, signed_properties_number, certificate_hash,
            serial_number, reference_id_number, issuer_name
        )
        
        # C14N de SignedProperties con namespaces
        signed_properties_con_ns = signed_properties.replace(
            '<etsi:SignedProperties', 
            '<etsi:SignedProperties ' + XMLNS
        )
        signed_properties_c14n = get_c14n(signed_properties_con_ns)
        sha1_signed_properties = sha1_base64(signed_properties_c14n.encode('utf-8'))
        logger.info(f"🔐 SHA1 SignedProperties: {sha1_signed_properties}")
        
        # 2. Generar KeyInfo
        key_info = get_key_info(certificate_number, certificate_x509, modulo, exponente)
        
        # C14N de KeyInfo con namespaces
        key_info_con_ns = key_info.replace('<ds:KeyInfo', '<ds:KeyInfo ' + XMLNS)
        key_info_c14n = get_c14n(key_info_con_ns)
        sha1_certificate = sha1_base64(key_info_c14n.encode('utf-8'))
        logger.info(f"🔐 SHA1 KeyInfo: {sha1_certificate}")
        
        # 3. Generar SignedInfo
        signed_info = get_signed_info(
            signed_info_number, signed_properties_id_number, sha1_signed_properties,
            certificate_number, sha1_certificate, reference_id_number,
            sha1_comprobante, signature_number, signed_properties_number
        )
        
        # C14N de SignedInfo para firmar
        signed_info_con_ns = signed_info.replace('<ds:SignedInfo', '<ds:SignedInfo ' + XMLNS)
        signed_info_c14n = get_c14n(signed_info_con_ns)
        logger.info(f"📝 SignedInfo C14N ({len(signed_info_c14n)} bytes)")
        
        # 4. Firmar SignedInfo con clave privada
        # Convertir clave privada de cryptography a OpenSSL
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Cargar con OpenSSL para firmar
        pkey = crypto.load_privatekey(crypto.FILETYPE_PEM, private_key_pem)
        signature_bytes = crypto.sign(pkey, signed_info_c14n.encode('utf-8'), "SHA1")
        
        # Codificar firma en base64
        signature = encode_base64(signature_bytes)
        signature = split_string_every_n(signature, MAX_LINE_SIZE)
        logger.info(f"✅ Firma generada ({len(signature_bytes)} bytes)")
        
        # 5. Construir XAdES-BES completo
        xades_bes = get_xades_bes(
            XMLNS, signature_number, signature_value_number, object_number,
            signed_info, signature, key_info, signed_properties
        )
        
        # 6. Insertar firma antes del tag final
        tail_tag = get_xml_nodo_final(xml_tree)
        comprobante_firmado = xml_content.replace(tail_tag, xades_bes + tail_tag)
        
        # 7. Guardar XML firmado
        storage_write_bytes(xml_firmado_path, comprobante_firmado.encode('utf-8'))
        
        logger.info(f"✅ XML firmado guardado: {xml_firmado_path}")
        logger.info("=" * 80)
        logger.info("🎉 FIRMA XADES-BES COMPLETADA EXITOSAMENTE")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error al firmar XML: {e}", exc_info=True)
        return False
