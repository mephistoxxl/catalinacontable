"""Utilidades de firma XAdES-BES basadas en endesive."""

from __future__ import annotations

import base64
import hashlib
import io
import logging
from copy import deepcopy
from typing import Callable, Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12
from lxml import etree

from inventario.models import Empresa, Opciones
from inventario.tenant.queryset import get_current_tenant
from inventario.utils.storage_io import storage_read_bytes, storage_write_bytes

logger = logging.getLogger(__name__)

DS_NS = "http://www.w3.org/2000/09/xmldsig#"
XADES_NS = "http://uri.etsi.org/01903/v1.3.2#"
NSMAP = {"ds": DS_NS, "xades": XADES_NS}

HashResolver = Tuple[Callable[[bytes], "hashlib._Hash"], Callable[[], hashes.HashAlgorithm]]


class XAdESError(Exception):
    """Error controlado durante el proceso de firma XAdES-BES."""


def _normalizar_atributos_factura(element: Optional[etree._Element]) -> None:
    """Ajusta el nodo de factura para cumplir el esquema del SRI."""
    if element is None:
        return

    try:
        local_name = etree.QName(element).localname
    except Exception:
        local_name = element.tag.rsplit("}", 1)[-1] if "}" in element.tag else element.tag

    if local_name != "factura":
        return

    preserved_version = element.get("version")

    id_attributes: list[str] = []
    id_value: Optional[str] = None

    for attr in list(element.attrib):
        attr_local = attr.rsplit("}", 1)[-1] if "}" in attr else attr
        if attr_local.lower() == "id":
            id_attributes.append(attr)
            candidate = element.get(attr)
            if candidate and candidate.strip():
                id_value = candidate.strip()

    if not id_value or id_value.lower() != "comprobante":
        id_value = "comprobante"

    for attr in id_attributes:
        element.set(attr, id_value)

    if "Id" not in element.attrib:
        element.set("Id", id_value)
    if "id" not in element.attrib:
        element.set("id", id_value)

    if preserved_version is not None:
        element.set("version", preserved_version)


def _normalizar_factura_bytes(xml_bytes: bytes) -> bytes:
    """Normaliza la raiz de la factura y devuelve bytes canonicos."""
    try:
        doc = etree.parse(io.BytesIO(xml_bytes))
    except Exception as exc:
        logger.warning("No se pudo analizar el XML para normalizar atributos: %s", exc)
        return xml_bytes

    root = doc.getroot()
    _normalizar_atributos_factura(root)

    id_attrs = [
        attr
        for attr in root.attrib
        if (attr.rsplit("}", 1)[-1] if "}" in attr else attr).lower() == "id"
    ]
    if not id_attrs:
        raise XAdESError(
            "Normalizacion fallida: el comprobante debe exponer el atributo 'Id'='comprobante'"
        )

    id_values = {root.get(attr) for attr in id_attrs}
    if any((value or "").strip() != "comprobante" for value in id_values):
        raise XAdESError("Normalizacion fallida: el comprobante debe tener Id='comprobante'")
    if root.get("version") is None:
        raise XAdESError("Normalizacion fallida: falta el atributo obligatorio 'version'")

    return etree.tostring(doc, encoding="UTF-8", xml_declaration=True, standalone=False)


_HASH_ALGORITHMS: dict[str, HashResolver] = {
    "sha1": (hashlib.sha1, hashes.SHA1),
    "sha224": (hashlib.sha224, hashes.SHA224),
    "sha256": (hashlib.sha256, hashes.SHA256),
    "sha384": (hashlib.sha384, hashes.SHA384),
    "sha512": (hashlib.sha512, hashes.SHA512),
}


def resolver_hash_algoritmo(algorithm_uri: Optional[str]) -> HashResolver:
    """Obtiene funciones hash a partir de la URI declarada en la firma."""
    if not algorithm_uri or not algorithm_uri.strip():
        raise XAdESError("Algoritmo de hash no especificado en la firma XAdES")

    fragment = algorithm_uri.strip()
    if "#" in fragment:
        fragment = fragment.split("#", 1)[1]
    fragment = fragment.split(":")[-1].lower()

    for prefix in ("rsa-", "dsa-", "ecdsa-", "hmac-"):
        if fragment.startswith(prefix):
            fragment = fragment[len(prefix):]
            break

    if fragment not in _HASH_ALGORITHMS:
        raise XAdESError(f"Algoritmo de hash no soportado: {algorithm_uri}")

    return _HASH_ALGORITHMS[fragment]


def _partir_base64(data: bytes) -> str:
    texto = base64.b64encode(data).decode()
    return "\n".join(texto[i : i + 64] for i in range(0, len(texto), 64))


def _resolver_opciones_firma(
    opciones: Optional[Opciones],
    empresa: Optional[Empresa],
) -> Opciones:
    if opciones is not None:
        return opciones

    queryset = Opciones._base_manager.all()
    if empresa is not None:
        queryset = queryset.filter(empresa=empresa)
    else:
        tenant = get_current_tenant()
        if tenant is not None:
            queryset = queryset.filter(empresa=tenant)

    registro = queryset.first()
    if registro is None:
        raise XAdESError("No hay configuraci�n de firma electr�nica disponible para la empresa actual")

    faltantes = []
    if not registro.firma_electronica:
        faltantes.append("archivo de firma (.p12/.pfx)")
    if not registro.password_firma:
        faltantes.append("contrase�a del certificado")
    if faltantes:
        detalle = ", ".join(faltantes)
        raise XAdESError(f"Configuraci�n incompleta de firma electr�nica: faltan {detalle}")

    return registro


def _resolver_objetivo_desde_uri(root: etree._Element, uri: Optional[str]) -> etree._Element:
    """Obtiene el elemento objetivo de una referencia ds:Reference."""

    if uri in (None, "", "#"):
        return root

    if not uri.startswith("#"):
        raise XAdESError(f"Referencia ds:Reference no soportada: URI='{uri}'")

    target_id = uri[1:]
    if not target_id:
        return root

    for element in root.iter():
        for attr in ("Id", "ID", "id"):
            value = element.get(attr)
            if value is not None and value.strip() == target_id:
                return element

    raise XAdESError(f"No se encontro el elemento referenciado por URI='{uri}'")


def _canonicalizar_objetivo(reference: etree._Element, tree: etree._ElementTree) -> bytes:
    root = tree.getroot()
    transforms = reference.find("ds:Transforms", namespaces=NSMAP)

    objetivo = _resolver_objetivo_desde_uri(root, reference.get("URI"))
    target = deepcopy(objetivo)
    _normalizar_atributos_factura(target)

    exclusive = False
    with_comments = False

    if transforms is not None:
        for transform in transforms.findall("ds:Transform", namespaces=NSMAP):
            algo = (transform.get("Algorithm") or "").lower()
            if algo.endswith("#enveloped-signature"):
                signature_inside = target.find(".//ds:Signature", namespaces=NSMAP)
                if signature_inside is not None and signature_inside.getparent() is not None:
                    signature_inside.getparent().remove(signature_inside)
            elif algo.endswith("xml-exc-c14n#withcomments"):
                exclusive = True
                with_comments = True
            elif algo.endswith("xml-exc-c14n#"):
                exclusive = True
                with_comments = False
            elif algo.endswith("rec-xml-c14n-20010315#withcomments"):
                exclusive = False
                with_comments = True
            elif algo.endswith("rec-xml-c14n-20010315"):
                exclusive = False
                with_comments = False

    buffer = io.BytesIO()
    etree.ElementTree(target).write_c14n(buffer, exclusive=exclusive, with_comments=with_comments)
    return buffer.getvalue()


def _recalcular_digest(reference: etree._Element, tree: etree._ElementTree) -> None:
    digest_method = reference.find("ds:DigestMethod", namespaces=NSMAP)
    digest_value = reference.find("ds:DigestValue", namespaces=NSMAP)

    if digest_method is None or digest_value is None:
        raise XAdESError("Elementos de digest incompletos en la firma")

    hashlib_fn, _ = resolver_hash_algoritmo(digest_method.get("Algorithm"))
    try:
        canonical = _canonicalizar_objetivo(reference, tree)
    except XAdESError as exc:
        uri = reference.get("URI")
        raise XAdESError(f"Error al canonicalizar la referencia URI='{uri}': {exc}") from exc
    digest_value.text = base64.b64encode(hashlib_fn(canonical).digest()).decode()


def _firmar_signed_info(
    signed_info: etree._Element,
    private_key,
    signature_el: etree._Element,
) -> None:
    canonicalization = signed_info.find("ds:CanonicalizationMethod", namespaces=NSMAP)
    can_algo = (canonicalization.get("Algorithm") if canonicalization is not None else "") or ""
    exclusive = "xml-exc-c14n" in can_algo and "rec-xml-c14n-20010315" not in can_algo
    with_comments = can_algo.endswith("withcomments")

    buffer = io.BytesIO()
    etree.ElementTree(signed_info).write_c14n(buffer, exclusive=exclusive, with_comments=with_comments)

    signature_method = signed_info.find("ds:SignatureMethod", namespaces=NSMAP)
    if signature_method is None:
        raise XAdESError("No se encontr� ds:SignatureMethod en la firma generada")

    _, hash_cls = resolver_hash_algoritmo(signature_method.get("Algorithm"))
    signature_bytes = private_key.sign(buffer.getvalue(), padding.PKCS1v15(), hash_cls())

    signature_value = signature_el.find("ds:SignatureValue", namespaces=NSMAP)
    if signature_value is None:
        raise XAdESError("No se encontr� ds:SignatureValue en la firma generada")

    signature_value.text = _partir_base64(signature_bytes)


def _firmar_con_endesive(
    xml_bytes: bytes,
    private_key,
    certificate,
    cert_der: bytes,
) -> etree._ElementTree:
    try:
        from endesive.xades import BES
    except ImportError as exc:
        raise XAdESError(
            "Librer�a endesive no disponible. Instale con `pip install endesive>=2.17.0`."
        ) from exc

    def signproc(data: bytes, algo: str) -> bytes:
        _, hash_cls = resolver_hash_algoritmo(algo)
        return private_key.sign(data, padding.PKCS1v15(), hash_cls())

    signer = BES()
    try:
        return signer.enveloped(xml_bytes, certificate, cert_der, signproc, tspurl=None, tspcred=None)
    except Exception as exc:
        raise XAdESError(f"Error en firma con endesive: {exc}") from exc


def firmar_xml_xades_bes(
    xml_path: str,
    xml_firmado_path: str,
    *,
    empresa: Optional[Empresa] = None,
    opciones: Optional[Opciones] = None,
) -> bool:
    """Firma un XML con XAdES-BES siguiendo un flujo atomico."""
    opciones = _resolver_opciones_firma(opciones, empresa)

    xml_bytes = storage_read_bytes(xml_path)
    xml_bytes_normalizados = _normalizar_factura_bytes(xml_bytes)

    try:
        with opciones.firma_electronica.open("rb") as descriptor:
            p12_bytes = descriptor.read()
    except FileNotFoundError as exc:
        raise XAdESError("No se pudo leer el archivo de firma electronica configurado") from exc

    try:
        private_key, certificate, _ = pkcs12.load_key_and_certificates(
            p12_bytes, (opciones.password_firma or "").encode("utf-8")
        )
    except Exception as exc:
        raise XAdESError(f"Certificado PKCS#12 invalido: {exc}") from exc

    if private_key is None or certificate is None:
        raise XAdESError("El archivo PKCS#12 no contiene llave y certificado validos")

    try:
        cert_der = certificate.public_bytes(Encoding.DER)
    except Exception as exc:
        raise XAdESError(f"No se pudo serializar el certificado PKCS#12: {exc}") from exc

    tree = _firmar_con_endesive(xml_bytes_normalizados, private_key, certificate, cert_der)

    root_signed = tree.getroot()
    id_attrs_signed = [
        attr
        for attr in root_signed.attrib
        if (attr.rsplit("}", 1)[-1] if "}" in attr else attr).lower() == "id"
    ]
    if not id_attrs_signed:
        raise XAdESError("El comprobante firmado debe incluir Id='comprobante'")

    id_values_signed = {root_signed.get(attr) for attr in id_attrs_signed}
    if any((value or "").strip() != "comprobante" for value in id_values_signed):
        raise XAdESError("El comprobante firmado debe conservar Id='comprobante'")

    if root_signed.get("Id") != "comprobante":
        raise XAdESError("El comprobante firmado debe exponer Id='comprobante'")
    if root_signed.get("id") != "comprobante":
        raise XAdESError("El comprobante firmado debe exponer id='comprobante'")

    signature_el = tree.find(".//ds:Signature", namespaces=NSMAP)
    if signature_el is None:
        raise XAdESError("No se genero ds:Signature en el documento firmado")

    references = signature_el.findall("ds:SignedInfo/ds:Reference", namespaces=NSMAP)
    if not references:
        raise XAdESError("La firma generada no contiene referencias")

    principal_reference = next((ref for ref in references if not ref.get("Type")), None)
    if principal_reference is None:
        raise XAdESError("No se encontro la referencia principal al comprobante")

    uri_value = principal_reference.get("URI")
    if uri_value in (None, ""):
        principal_reference.set("URI", "#comprobante")
    elif uri_value != "#comprobante":
        raise XAdESError("La referencia principal debe apuntar a '#comprobante'")

    for reference in references:
        _recalcular_digest(reference, tree)

    signed_info = signature_el.find("ds:SignedInfo", namespaces=NSMAP)
    if signed_info is None:
        raise XAdESError("No se encontro ds:SignedInfo en la firma generada")

    _firmar_signed_info(signed_info, private_key, signature_el)

    xml_firmado = etree.tostring(tree, encoding="UTF-8", xml_declaration=True, standalone=False)
    storage_write_bytes(xml_firmado_path, xml_firmado)
    logger.info("XML firmado exitosamente con XAdES-BES: %s", xml_firmado_path)
    return True


class SRIXAdESFirmador:
    """Compatibilidad hacia atr�s para firmas asociadas a una empresa."""

    def __init__(self, empresa: Optional[Empresa] = None):
        self.empresa = empresa
        self.opciones = _resolver_opciones_firma(None, empresa)

    def firmar_xml_xades_bes(self, xml_path: str, xml_firmado_path: str) -> bool:
        return firmar_xml_xades_bes(
            xml_path,
            xml_firmado_path,
            empresa=self.empresa,
            opciones=self.opciones,
        )


def firmar_xml_con_endesive(
    xml_path: str,
    xml_firmado_path: str,
    *,
    empresa: Optional[Empresa] = None,
    opciones: Optional[Opciones] = None,
) -> bool:
    """Alias mantenido por retrocompatibilidad."""
    return firmar_xml_xades_bes(xml_path, xml_firmado_path, empresa=empresa, opciones=opciones)
