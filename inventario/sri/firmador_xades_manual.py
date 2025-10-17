"""Implementación manual de XAdES-BES con SHA1 para evitar bugs de endesive."""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12
from cryptography.x509 import Certificate
from lxml import etree

from inventario.models import Empresa, Opciones
from inventario.utils.storage_io import storage_read_bytes, storage_write_bytes

logger = logging.getLogger(__name__)

# Namespaces
NSMAP = {
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "xades": "http://uri.etsi.org/01903/v1.3.2#",
}

# Algoritmos - Usar Inclusive C14N como en facturas autorizadas del SRI
C14N_ALGORITHM = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
RSA_SHA1_ALGORITHM = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
SHA1_ALGORITHM = "http://www.w3.org/2000/09/xmldsig#sha1"
ENVELOPED_SIGNATURE_TRANSFORM = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
SIGNED_PROPERTIES_TYPE = "http://uri.etsi.org/01903#SignedProperties"


class XAdESError(Exception):
    """Error en operaciones XAdES."""


def _generar_id(sufijo: str = "") -> str:
    """Genera un ID único para elementos de firma compatible con NCName."""
    # Generar UUID sin guiones y agregar prefijo para que sea NCName válido
    # NCName no puede empezar con número, así que usamos prefijo alfabético
    uuid_hex = uuid.uuid4().hex
    base_id = f"id{uuid_hex}"
    return f"{base_id}_{sufijo}" if sufijo else base_id


def _calcular_digest_sha1(data: bytes) -> str:
    """Calcula el digest SHA1 y lo devuelve en Base64."""
    digest = hashlib.sha1(data).digest()
    return base64.b64encode(digest).decode("ascii")


def _canonicalizar_elemento(elemento: etree._Element) -> bytes:
    """Canonicaliza un elemento usando Inclusive C14N (como en facturas autorizadas del SRI)."""
    # Usar exclusive=False para Inclusive C14N
    return etree.tostring(elemento, method="c14n", exclusive=False, with_comments=False)


def _partir_base64(data: bytes, line_length: int = 64) -> str:
    """Convierte bytes a Base64 con saltos de línea cada N caracteres."""
    b64 = base64.b64encode(data).decode("ascii")
    lines = [b64[i:i+line_length] for i in range(0, len(b64), line_length)]
    return "\n".join(lines)


def firmar_xml_xades_bes_manual(
    xml_path: str,
    xml_firmado_path: str,
    *,
    empresa: Optional[Empresa] = None,
    opciones: Optional[Opciones] = None,
) -> bool:
    """
    Firma un XML con XAdES-BES construyendo manualmente la estructura.
    Esta implementación evita bugs de endesive y asegura SHA1 desde el inicio.
    """
    # Resolver opciones
    if opciones is None:
        if empresa is None:
            raise XAdESError("Se requiere empresa u opciones para firmar")
        try:
            opciones = Opciones.objects.get(empresa=empresa)
        except Opciones.DoesNotExist as exc:
            raise XAdESError(f"No existen opciones de firma para la empresa {empresa}") from exc

    # Leer XML original
    xml_bytes = storage_read_bytes(xml_path)
    
    # Parsear y asegurar id="comprobante"
    try:
        doc = etree.parse(io.BytesIO(xml_bytes))
        root = doc.getroot()
    except Exception as exc:
        raise XAdESError(f"Error al parsear XML: {exc}") from exc

    if root.get("id") != "comprobante":
        root.set("id", "comprobante")
        logger.info("🔧 Atributo id='comprobante' establecido")

    # Cargar certificado PKCS#12
    try:
        with opciones.firma_electronica.open("rb") as f:
            p12_bytes = f.read()
        private_key, certificate, _ = pkcs12.load_key_and_certificates(
            p12_bytes, (opciones.password_firma or "").encode("utf-8")
        )
    except Exception as exc:
        raise XAdESError(f"Error al cargar certificado: {exc}") from exc

    if private_key is None or certificate is None:
        raise XAdESError("Certificado inválido")

    # Obtener bytes DER del certificado
    cert_der = certificate.public_bytes(Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode("ascii")
    
    # Calcular digest SHA1 del certificado
    cert_digest = _calcular_digest_sha1(cert_der)

    # Generar IDs únicos
    sig_id = _generar_id("4e")
    signed_info_id = _generar_id("16")
    ref1_id = _generar_id("70")
    ref2_id = _generar_id("7f")
    sig_value_id = _generar_id("05")
    key_info_id = _generar_id("73")
    qp_id = _generar_id("14")
    signed_props_id = _generar_id("19")
    signed_sig_props_id = _generar_id("5d")
    signed_data_props_id = _generar_id("1c")
    unsigned_props_id = _generar_id("02")

    # === PASO 1: Calcular digest de la factura ===
    # Usar Exclusive C14N como requiere el SRI
    # Con enveloped-signature transform, este digest es directamente el correcto
    factura_c14n = _canonicalizar_elemento(root)
    factura_digest = _calcular_digest_sha1(factura_c14n)
    
    logger.info(f"✅ Digest factura calculado con Exclusive C14N: {factura_digest}")

    # === PASO 2: Construir SignedProperties ===
    signed_props = etree.Element(
        f"{{{NSMAP['xades']}}}SignedProperties",
        attrib={"Id": signed_props_id},
        nsmap={"xades": NSMAP["xades"], "ds": NSMAP["ds"]}
    )

    # SignedSignatureProperties
    signed_sig_props = etree.SubElement(
        signed_props,
        f"{{{NSMAP['xades']}}}SignedSignatureProperties",
        attrib={"Id": signed_sig_props_id}
    )

    # SigningTime
    signing_time = etree.SubElement(signed_sig_props, f"{{{NSMAP['xades']}}}SigningTime")
    signing_time.text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # SigningCertificate
    signing_cert = etree.SubElement(signed_sig_props, f"{{{NSMAP['xades']}}}SigningCertificate")
    cert_elem = etree.SubElement(signing_cert, f"{{{NSMAP['xades']}}}Cert")
    
    cert_digest_elem = etree.SubElement(cert_elem, f"{{{NSMAP['xades']}}}CertDigest")
    cert_digest_method = etree.SubElement(cert_digest_elem, f"{{{NSMAP['ds']}}}DigestMethod", attrib={"Algorithm": SHA1_ALGORITHM})
    cert_digest_value = etree.SubElement(cert_digest_elem, f"{{{NSMAP['ds']}}}DigestValue")
    cert_digest_value.text = cert_digest

    cert_issuer_serial = etree.SubElement(cert_elem, f"{{{NSMAP['xades']}}}IssuerSerial")
    x509_issuer = etree.SubElement(cert_issuer_serial, f"{{{NSMAP['ds']}}}X509IssuerName")
    x509_issuer.text = certificate.issuer.rfc4514_string()
    x509_serial = etree.SubElement(cert_issuer_serial, f"{{{NSMAP['ds']}}}X509SerialNumber")
    x509_serial.text = str(certificate.serial_number)

    # SignedDataObjectProperties
    signed_data_props = etree.SubElement(
        signed_props,
        f"{{{NSMAP['xades']}}}SignedDataObjectProperties",
        attrib={"Id": signed_data_props_id}
    )

    data_obj_format = etree.SubElement(
        signed_data_props,
        f"{{{NSMAP['xades']}}}DataObjectFormat",
        attrib={"ObjectReference": f"#Reference1_{ref1_id}"}
    )
    
    desc = etree.SubElement(data_obj_format, f"{{{NSMAP['xades']}}}Description")
    desc.text = 'MIME-Version: 1.0\nContent-Type: text/xml\nContent-Transfer-Encoding: binary\nContent-Disposition: filename="document.xml"'
    
    obj_id = etree.SubElement(data_obj_format, f"{{{NSMAP['xades']}}}ObjectIdentifier")
    identifier = etree.SubElement(obj_id, f"{{{NSMAP['xades']}}}Identifier", attrib={"Qualifier": "OIDAsURI"})
    identifier.text = "http://www.certum.pl/OIDAsURI/signedFile/1.2.616.1.113527.3.1.1.3.1"
    
    mime_type = etree.SubElement(data_obj_format, f"{{{NSMAP['xades']}}}MimeType")
    mime_type.text = "text/xml"

    # Canonicalizar SignedProperties y calcular su digest
    signed_props_c14n = _canonicalizar_elemento(signed_props)
    signed_props_digest = _calcular_digest_sha1(signed_props_c14n)
    
    logger.info(f"✅ Digest SignedProperties calculado: {signed_props_digest[:20]}...")

    # === PASO 3: Construir SignedInfo ===
    signed_info = etree.Element(
        f"{{{NSMAP['ds']}}}SignedInfo",
        attrib={"Id": signed_info_id},
        nsmap={"ds": NSMAP["ds"]}
    )

    # CanonicalizationMethod
    c14n_method = etree.SubElement(signed_info, f"{{{NSMAP['ds']}}}CanonicalizationMethod", attrib={"Algorithm": C14N_ALGORITHM})

    # SignatureMethod
    sig_method = etree.SubElement(signed_info, f"{{{NSMAP['ds']}}}SignatureMethod", attrib={"Algorithm": RSA_SHA1_ALGORITHM})

    # Reference 1: Factura - solo enveloped-signature como en facturas autorizadas del SRI
    ref1 = etree.SubElement(signed_info, f"{{{NSMAP['ds']}}}Reference", attrib={"Id": f"Reference1_{ref1_id}", "URI": "#comprobante"})
    
    transforms1 = etree.SubElement(ref1, f"{{{NSMAP['ds']}}}Transforms")
    # Solo enveloped-signature (remueve automáticamente la firma del documento)
    transform1 = etree.SubElement(transforms1, f"{{{NSMAP['ds']}}}Transform", attrib={"Algorithm": ENVELOPED_SIGNATURE_TRANSFORM})
    
    digest_method1 = etree.SubElement(ref1, f"{{{NSMAP['ds']}}}DigestMethod", attrib={"Algorithm": SHA1_ALGORITHM})
    digest_value1 = etree.SubElement(ref1, f"{{{NSMAP['ds']}}}DigestValue")
    digest_value1.text = factura_digest

    # Reference 2: KeyInfo (certificado) - como en facturas autorizadas
    ref2 = etree.SubElement(signed_info, f"{{{NSMAP['ds']}}}Reference", attrib={"URI": f"#{key_info_id}"})
    digest_method2 = etree.SubElement(ref2, f"{{{NSMAP['ds']}}}DigestMethod", attrib={"Algorithm": SHA1_ALGORITHM})
    digest_value2 = etree.SubElement(ref2, f"{{{NSMAP['ds']}}}DigestValue")
    # Calcular digest del KeyInfo (lo haremos después de crearlo)
    digest_value2.text = "PLACEHOLDER_KEYINFO_DIGEST"

    # Reference 3: SignedProperties - SIN transforms como en facturas autorizadas
    ref3 = etree.SubElement(
        signed_info,
        f"{{{NSMAP['ds']}}}Reference",
        attrib={
            "Id": f"SignedProperties-Reference_{ref2_id}",
            "Type": SIGNED_PROPERTIES_TYPE,
            "URI": f"#{signed_props_id}"
        }
    )
    
    digest_method3 = etree.SubElement(ref3, f"{{{NSMAP['ds']}}}DigestMethod", attrib={"Algorithm": SHA1_ALGORITHM})
    digest_value3 = etree.SubElement(ref3, f"{{{NSMAP['ds']}}}DigestValue")
    digest_value3.text = signed_props_digest

    # === PASO 4: Firmar SignedInfo ===
    signed_info_c14n = _canonicalizar_elemento(signed_info)
    signature_bytes = private_key.sign(signed_info_c14n, padding.PKCS1v15(), hashes.SHA1())
    signature_b64 = _partir_base64(signature_bytes)
    
    logger.info("✅ SignedInfo firmado con RSA-SHA1")

    # === PASO 5: Construir Signature completa ===
    signature = etree.Element(
        f"{{{NSMAP['ds']}}}Signature",
        attrib={"Id": f"Signature_{sig_id}"},
        nsmap={"ds": NSMAP["ds"]}
    )

    signature.append(signed_info)

    # SignatureValue
    sig_value = etree.SubElement(signature, f"{{{NSMAP['ds']}}}SignatureValue", attrib={"Id": sig_value_id})
    sig_value.text = signature_b64

    # KeyInfo
    key_info = etree.SubElement(signature, f"{{{NSMAP['ds']}}}KeyInfo", attrib={"Id": key_info_id})
    x509_data = etree.SubElement(key_info, f"{{{NSMAP['ds']}}}X509Data")
    x509_cert = etree.SubElement(x509_data, f"{{{NSMAP['ds']}}}X509Certificate")
    x509_cert.text = cert_b64

    # Calcular digest del KeyInfo y actualizar SignedInfo
    key_info_c14n = _canonicalizar_elemento(key_info)
    key_info_digest = _calcular_digest_sha1(key_info_c14n)
    
    # Actualizar el digest del KeyInfo en SignedInfo
    ns = {'ds': NSMAP['ds']}
    key_info_ref = signed_info.xpath(f'.//ds:Reference[@URI="#{key_info_id}"]/ds:DigestValue', namespaces=ns)[0]
    key_info_ref.text = key_info_digest
    
    # Re-firmar SignedInfo con el digest correcto del KeyInfo
    signed_info_c14n_final = _canonicalizar_elemento(signed_info)
    signature_bytes_final = private_key.sign(signed_info_c14n_final, padding.PKCS1v15(), hashes.SHA1())
    signature_b64_final = _partir_base64(signature_bytes_final)
    sig_value.text = signature_b64_final
    
    logger.info(f"✅ Digest KeyInfo calculado y SignedInfo re-firmado")

    # Object con QualifyingProperties
    obj = etree.SubElement(signature, f"{{{NSMAP['ds']}}}Object")
    
    qp = etree.SubElement(
        obj,
        f"{{{NSMAP['xades']}}}QualifyingProperties",
        attrib={"Id": qp_id, "Target": f"#Signature_{sig_id}"},
        nsmap={"xades": NSMAP["xades"]}
    )
    
    qp.append(signed_props)
    
    unsigned_props = etree.SubElement(qp, f"{{{NSMAP['xades']}}}UnsignedProperties", attrib={"Id": unsigned_props_id})

    # === PASO 6: Insertar firma en el documento ===
    root.append(signature)
    
    logger.info("✅ Firma XAdES-BES insertada en el documento")
    
    # Con enveloped-signature transform, NO necesitamos recalcular el digest.
    # El transform se aplica automáticamente durante la validación por el SRI.

    # === PASO 7: Guardar XML firmado final ===
    xml_firmado = etree.tostring(doc, encoding="UTF-8", xml_declaration=True, standalone=False)
    storage_write_bytes(xml_firmado_path, xml_firmado)
    
    logger.info(f"✅ XML firmado guardado: {xml_firmado_path}")
    logger.info(f"✅ Firma XAdES-BES manual completada con SHA1")

    return True
