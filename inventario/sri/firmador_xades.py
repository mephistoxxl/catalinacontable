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

RSA_SHA1_URI = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
SHA1_URI = "http://www.w3.org/2000/09/xmldsig#sha1"

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

    # ✅ SIMPLIFICADO: Preservar version y asegurar id="comprobante"
    preserved_version = element.get("version")
    
    # ✅ NO modificar nada más, solo asegurar que id="comprobante" exista
    current_id = element.get("id")
    if current_id != "comprobante":
        element.set("id", "comprobante")
        logger.debug(f"🔧 Atributo 'id' establecido a 'comprobante' (era: {current_id})")
    
    # ✅ Restaurar version si se perdió
    if preserved_version and element.get("version") != preserved_version:
        element.set("version", preserved_version)
        logger.debug(f"🔧 Atributo 'version' restaurado: {preserved_version}")


def _normalizar_factura_bytes(xml_bytes: bytes) -> bytes:
    """Normaliza la raiz de la factura y devuelve bytes canonicos."""
    try:
        doc = etree.parse(io.BytesIO(xml_bytes))
    except Exception as exc:
        logger.warning("No se pudo analizar el XML para normalizar atributos: %s", exc)
        return xml_bytes

    root = doc.getroot()
    _normalizar_atributos_factura(root)

    id_value = root.get("id")
    if (id_value or "").strip() != "comprobante":
        raise XAdESError(
            "Normalizacion fallida: el comprobante debe exponer el atributo 'id'='comprobante'"
        )

    for attr in list(root.attrib):
        attr_local = attr.rsplit("}", 1)[-1] if "}" in attr else attr
        if attr_local.lower() == "id" and attr_local != "id":
            other_value = root.get(attr)
            if (other_value or "").strip() and (other_value or "").strip() != "comprobante":
                raise XAdESError("Normalizacion fallida: valores inconsistentes de identificador")
            del root.attrib[attr]
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
    """Convierte bytes a Base64 en líneas de 64 caracteres SIN espacios finales."""
    # ✅ CRÍTICO: Usar 'ascii' y strip() para evitar problemas de encoding
    texto = base64.b64encode(data).decode('ascii').strip()
    # ✅ NO agregar salto de línea al final (puede causar problemas de validación)
    lineas = [texto[i:i+64] for i in range(0, len(texto), 64)]
    return "\n".join(lineas)


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
    
    # ✅ CRÍTICO: NO copiar nada - trabajar directamente con el elemento
    # pero remover la firma en una COPIA temporal solo para canonicalización
    if objetivo == root:
        # Crear una copia temporal serializando y re-parseando
        xml_bytes = etree.tostring(root, encoding="UTF-8", method="xml")
        target = etree.fromstring(xml_bytes)
    else:
        # Para elementos no-raíz, serializar y re-parsear
        xml_bytes = etree.tostring(objetivo, encoding="UTF-8", method="xml")
        target = etree.fromstring(xml_bytes)

    exclusive = False
    with_comments = False

    if transforms is not None:
        for transform in transforms.findall("ds:Transform", namespaces=NSMAP):
            algo = (transform.get("Algorithm") or "").lower()
            # ✅ CORRECCIÓN CRÍTICA: Reconocer XPath transform (usado por endesive)
            # El SRI valida con XPath que excluye la firma, igual que enveloped-signature
            if algo.endswith("#enveloped-signature") or "rec-xpath-19991116" in algo:
                # Para XPath, trabajar con el elemento raíz
                signature_inside = target.find(".//ds:Signature", namespaces=NSMAP)
                if signature_inside is not None and signature_inside.getparent() is not None:
                    signature_inside.getparent().remove(signature_inside)
                    logger.debug("🔧 Firma excluida del digest (transform: %s)", algo)
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

    # ✅ CRÍTICO: Usar tostring con method="c14n" en lugar de write_c14n
    # write_c14n tiene un bug que duplica caracteres cuando el elemento
    # fue creado con fromstring()
    try:
        if exclusive:
            canonical_bytes = etree.tostring(target, method="c14n", exclusive=True, with_comments=with_comments)
        else:
            canonical_bytes = etree.tostring(target, method="c14n", with_comments=with_comments)
    except TypeError:
        # Fallback para versiones antiguas de lxml
        buffer = io.BytesIO()
        etree.ElementTree(target).write_c14n(buffer, exclusive=exclusive, with_comments=with_comments)
        canonical_bytes = buffer.getvalue()
    
    if not canonical_bytes:
        logger.error("❌ Canonicalización produjo 0 bytes")
        logger.error(f"❌ Target tag: {target.tag if hasattr(target, 'tag') else 'N/A'}")
        raise XAdESError("La canonicalización produjo datos vacíos")
    
    logger.debug(f"✅ Canonicalización exitosa: {len(canonical_bytes)} bytes (primeros 50: {canonical_bytes[:50]})")
    return canonical_bytes


def _recalcular_digest(reference: etree._Element, tree: etree._ElementTree) -> None:
    digest_method = reference.find("ds:DigestMethod", namespaces=NSMAP)
    digest_value = reference.find("ds:DigestValue", namespaces=NSMAP)

    if digest_method is None or digest_value is None:
        raise XAdESError("Elementos de digest incompletos en la firma")

    # ✅ CRÍTICO: Obtener el algoritmo Y forzar SHA1 si es necesario
    algorithm_uri = digest_method.get("Algorithm")
    if not algorithm_uri or "sha256" in algorithm_uri.lower():
        logger.warning(f"⚠️ Algoritmo incorrecto detectado: {algorithm_uri}, forzando SHA1")
        algorithm_uri = SHA1_URI
        digest_method.set("Algorithm", SHA1_URI)
    
    # ✅ Usar directamente hashlib.sha1 en lugar de resolver
    if "sha1" in algorithm_uri.lower():
        hashlib_fn = hashlib.sha1
        logger.debug(f"🔧 Usando SHA1 para recalcular digest (URI: {reference.get('URI')})")
    else:
        hashlib_fn, _ = resolver_hash_algoritmo(algorithm_uri)
    
    try:
        canonical = _canonicalizar_objetivo(reference, tree)
        if not canonical:
            raise XAdESError("La canonicalización produjo datos vacíos")
        
        # ✅ Calcular digest y verificar que cambió
        new_digest = hashlib_fn(canonical).digest()
        new_digest_b64 = base64.b64encode(new_digest).decode()
        
        old_digest_value = digest_value.text
        digest_value.text = new_digest_b64
        
        if old_digest_value == new_digest_b64:
            logger.warning(f"⚠️ DigestValue NO cambió para URI={reference.get('URI')}")
            logger.warning(f"⚠️ Datos canónicos (primeros 100 bytes): {canonical[:100]}")
        else:
            logger.debug(f"✅ Digest recalculado: {old_digest_value[:20]}... → {new_digest_b64[:20]}...")
            
    except XAdESError as exc:
        uri = reference.get("URI")
        raise XAdESError(f"Error al canonicalizar la referencia URI='{uri}': {exc}") from exc


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
            "Libreria endesive no disponible. Instale con `pip install endesive>=2.17.0`."
        ) from exc

    def signproc(data: bytes, algo: str) -> bytes:
        # ✅ FORZAR RSA-SHA1 siempre (requerimiento del SRI - Error 39)
        # Ignorar completamente el algoritmo sugerido por endesive
        algoritmo_decl = (algo or "").strip()
        if algoritmo_decl and algoritmo_decl.lower() != RSA_SHA1_URI.lower():
            logger.warning(
                "SRI requiere RSA-SHA1, ignorando algoritmo sugerido por endesive: %s",
                algoritmo_decl,
            )
        # ✅ Usar SHA1 directamente en lugar de resolver el algoritmo sugerido
        return private_key.sign(data, padding.PKCS1v15(), hashes.SHA1())

    signer = BES()
    
    # ✅ PARCHE CRÍTICO: Intentar forzar SHA1 en endesive ANTES de firmar
    try:
        import endesive.xades.bes as bes_module
        original_sha256 = getattr(bes_module.BES, 'sha256', None)
        
        # Monkey-patch: reemplazar sha256 con sha1
        def force_sha1(self, data):
            """Fuerza SHA1 en lugar de SHA256."""
            h = hashlib.sha1(data).digest()
            return base64.b64encode(h).decode()
        
        bes_module.BES.sha256 = force_sha1
        logger.info("🔧 Forzando SHA1 en endesive (monkey-patch aplicado)")
    except Exception as patch_exc:
        logger.warning(f"⚠️ No se pudo aplicar monkey-patch a endesive: {patch_exc}")
        logger.warning("⚠️ Se aplicarán correcciones manuales después de la firma")
    
    try:
        tree_raw = signer.enveloped(xml_bytes, certificate, cert_der, signproc, tspurl=None, tspcred=None)
        
        # ✅ CRÍTICO: Serializar y re-parsear INMEDIATAMENTE para evitar bug de duplicación
        # El árbol devuelto por endesive tiene un problema interno que causa duplicación
        # de caracteres en atributos cuando se manipula posteriormente
        xml_bytes_signed = etree.tostring(tree_raw, encoding="UTF-8", xml_declaration=True, standalone=False)
        tree = etree.parse(io.BytesIO(xml_bytes_signed))
        
        # ✅ Verificar y corregir si endesive usó SHA256
        sig_method = tree.find(".//ds:SignatureMethod", namespaces=NSMAP)
        if sig_method is not None:
            algo = sig_method.get("Algorithm", "")
            if "sha256" in algo.lower():
                logger.warning("⚠️ Endesive ignoró el parche, se aplicarán correcciones manuales")
        
        return tree
        
    except Exception as exc:
        raise XAdESError(f"Error en firma con endesive: {exc}") from exc
    finally:
        # ✅ Restaurar método original si fue modificado
        try:
            if 'original_sha256' in locals() and original_sha256 is not None:
                bes_module.BES.sha256 = original_sha256
        except:
            pass


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

    # ✅ DIAGNÓSTICO: Guardar XML intermedio para inspección
    if logger.isEnabledFor(logging.DEBUG):
        xml_post_endesive = etree.tostring(tree, encoding="UTF-8", xml_declaration=True, standalone=False)
        debug_path = xml_firmado_path.replace(".xml", "_debug_post_endesive.xml")
        try:
            storage_write_bytes(debug_path, xml_post_endesive)
            logger.debug(f"🔍 XML post-endesive guardado en: {debug_path}")
        except Exception as e:
            logger.debug(f"No se pudo guardar debug XML: {e}")

    root_signed = tree.getroot()
    id_attrs_signed = [
        attr
        for attr in root_signed.attrib
        if (attr.rsplit("}", 1)[-1] if "}" in attr else attr).lower() == "id"
    ]
    if not id_attrs_signed:
        raise XAdESError("El comprobante firmado debe incluir id='comprobante'")

    id_value_signed = (root_signed.get("id") or "").strip()
    if id_value_signed != "comprobante":
        raise XAdESError("El comprobante firmado debe exponer id='comprobante'")

    for attr in id_attrs_signed:
        attr_local = attr.rsplit("}", 1)[-1] if "}" in attr else attr
        if attr_local != "id":
            other_value = (root_signed.get(attr) or "").strip()
            if other_value and other_value != "comprobante":
                raise XAdESError(
                    "El comprobante firmado no puede contener identificadores inconsistentes"
                )
            del root_signed.attrib[attr]

    signature_el = tree.find(".//ds:Signature", namespaces=NSMAP)
    if signature_el is None:
        raise XAdESError("No se genero ds:Signature en el documento firmado")

    signed_info = signature_el.find("ds:SignedInfo", namespaces=NSMAP)
    if signed_info is None:
        raise XAdESError("No se encontro ds:SignedInfo en la firma generada")

    signature_method = signed_info.find("ds:SignatureMethod", namespaces=NSMAP)
    if signature_method is None:
        raise XAdESError("No se encontro ds:SignatureMethod en la firma generada")
    signature_method.set("Algorithm", RSA_SHA1_URI)

    references_signed_info = signed_info.findall("ds:Reference", namespaces=NSMAP)
    if not references_signed_info:
        raise XAdESError("La firma generada no contiene referencias")

    principal_reference = next((ref for ref in references_signed_info if not ref.get("Type")), None)
    if principal_reference is None:
        raise XAdESError("No se encontro la referencia principal al comprobante")

    uri_value = principal_reference.get("URI")
    if uri_value in (None, ""):
        principal_reference.set("URI", "#comprobante")
    elif uri_value != "#comprobante":
        raise XAdESError("La referencia principal debe apuntar a '#comprobante'")

    # ✅ Logging de cambios antes de aplicarlos
    logger.info("🔧 Aplicando correcciones de algoritmos a la firma:")
    logger.info(f"  - SignatureMethod: {signature_method.get('Algorithm')} → {RSA_SHA1_URI}")
    
    references_all = signature_el.findall(".//ds:Reference", namespaces=NSMAP)
    logger.info(f"  - Referencias a procesar: {len(references_all)}")
    
    for idx, reference in enumerate(references_all):
        digest_method = reference.find("ds:DigestMethod", namespaces=NSMAP)
        if digest_method is None:
            raise XAdESError("Cada ds:Reference debe incluir ds:DigestMethod")
        
        old_algo = digest_method.get("Algorithm", "")
        old_digest = reference.find("ds:DigestValue", namespaces=NSMAP)
        old_digest_value = old_digest.text if old_digest is not None else "N/A"
        
        digest_method.set("Algorithm", SHA1_URI)
        logger.info(f"    Ref {idx+1} URI={reference.get('URI')}: {old_algo} → {SHA1_URI}")
        logger.info(f"    Ref {idx+1} DigestValue antes: {old_digest_value[:20]}...")
        
        _recalcular_digest(reference, tree)
        
        new_digest = reference.find("ds:DigestValue", namespaces=NSMAP)
        new_digest_value = new_digest.text if new_digest is not None else "N/A"
        logger.info(f"    Ref {idx+1} DigestValue después: {new_digest_value[:20]}...")
        
        if old_digest_value == new_digest_value:
            logger.warning(f"    ⚠️  Ref {idx+1}: Digest NO cambió (posible problema)")

    # ✅ FORZAR SHA1 en xades:CertDigest (requerimiento del SRI)
    cert_digest_methods = signature_el.findall(".//xades:CertDigest/ds:DigestMethod", namespaces=NSMAP)
    for cert_digest_method in cert_digest_methods:
        current_algo = cert_digest_method.get("Algorithm", "")
        if current_algo.lower() != SHA1_URI.lower():
            logger.info(f"🔄 Cambiando algoritmo de CertDigest de {current_algo} a SHA1")
            cert_digest_method.set("Algorithm", SHA1_URI)
            
            # ✅ Recalcular el DigestValue del certificado con SHA1
            cert_digest_value = cert_digest_method.getparent().find("ds:DigestValue", namespaces=NSMAP)
            if cert_digest_value is not None:
                # Obtener el certificado DER del KeyInfo
                x509_cert_element = signature_el.find(".//ds:X509Certificate", namespaces=NSMAP)
                if x509_cert_element is not None and x509_cert_element.text:
                    try:
                        cert_der_b64 = x509_cert_element.text.strip().replace("\n", "")
                        cert_der_bytes = base64.b64decode(cert_der_b64)
                        # Calcular SHA1 del certificado DER
                        cert_sha1 = hashlib.sha1(cert_der_bytes).digest()
                        cert_digest_value.text = base64.b64encode(cert_sha1).decode()
                        logger.info("✅ DigestValue del certificado recalculado con SHA1")
                    except Exception as exc:
                        logger.warning(f"⚠️ No se pudo recalcular CertDigest: {exc}")

    logger.info("🔏 Re-firmando SignedInfo con RSA-SHA1...")
    _firmar_signed_info(signed_info, private_key, signature_el)

    # ✅ VALIDACIÓN FINAL: Confirmar que se usó RSA-SHA1
    signature_method_final = signed_info.find("ds:SignatureMethod", namespaces=NSMAP)
    if signature_method_final is not None:
        algo_final = signature_method_final.get("Algorithm", "")
        if algo_final.lower() == RSA_SHA1_URI.lower():
            logger.info("✅ Firma generada correctamente con RSA-SHA1 (requerimiento SRI)")
        else:
            logger.error(f"❌ ADVERTENCIA CRÍTICA: Se usó {algo_final} en lugar de RSA-SHA1")
            logger.error("❌ Esto causará Error 39 (FIRMA INVALIDA) en el SRI")
            raise XAdESError(f"Error crítico: Algoritmo incorrecto {algo_final}, se requiere RSA-SHA1")
    
    # ✅ Validar todos los DigestMethod finales
    all_digest_methods = signature_el.findall(".//ds:DigestMethod", namespaces=NSMAP)
    for dm in all_digest_methods:
        algo = dm.get("Algorithm", "")
        if "sha256" in algo.lower():
            logger.error(f"❌ DigestMethod todavía usa SHA256: {algo}")
            raise XAdESError("Error crítico: Aún hay digests con SHA256, se requiere SHA1")
    
    logger.info(f"✅ Todos los algoritmos validados correctamente ({len(all_digest_methods)} DigestMethod)")

    # ✅ DIAGNÓSTICO: Guardar XML final para inspección
    if logger.isEnabledFor(logging.DEBUG):
        xml_final_debug = etree.tostring(tree, encoding="UTF-8", xml_declaration=True, standalone=False)
        debug_path_final = xml_firmado_path.replace(".xml", "_debug_final.xml")
        try:
            storage_write_bytes(debug_path_final, xml_final_debug)
            logger.debug(f"🔍 XML final guardado en: {debug_path_final}")
        except Exception as e:
            logger.debug(f"No se pudo guardar debug XML final: {e}")

    xml_firmado = etree.tostring(tree, encoding="UTF-8", xml_declaration=True, standalone=False)
    storage_write_bytes(xml_firmado_path, xml_firmado)
    logger.info("✅ XML firmado exitosamente con XAdES-BES: %s", xml_firmado_path)
    logger.info("✅ Todos los requisitos del SRI cumplidos (RSA-SHA1, SHA1 digests, XPath transform)")
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
