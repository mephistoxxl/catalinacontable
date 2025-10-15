# inventario/sri/firmador_xades.py
"""Utilidades de firma XAdES-BES basadas en endesive.

Implementación actualizada usando endesive.xades (BES) con firma PKCS#12.
"""

import logging
from inventario.models import Opciones
from inventario.tenant.queryset import get_current_tenant
from lxml import etree
import io
import base64
import hashlib
import uuid
from datetime import datetime
from copy import deepcopy

from inventario.utils.storage_io import storage_read_bytes, storage_write_bytes

# crypto
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)


class XAdESError(Exception):
    """Excepción personalizada para errores relacionados con XAdES."""
    pass


def resolver_hash_algoritmo(algorithm_uri: str):
    """Obtiene funciones de ``hashlib`` y ``cryptography`` para la URI dada."""

    if algorithm_uri is None:
        raise XAdESError("Algoritmo de hash no especificado en la firma XAdES")

    normalized = str(algorithm_uri).strip()
    if not normalized:
        raise XAdESError("Algoritmo de hash no especificado en la firma XAdES")

    fragment = normalized
    if "#" in fragment:
        fragment = fragment.split("#", 1)[1]

    fragment = fragment.lower()
    for prefix in ("rsa-", "dsa-", "ecdsa-", "hmac-"):
        if fragment.startswith(prefix):
            fragment = fragment[len(prefix):]
            break

    mapping = {
        "sha1": (hashlib.sha1, hashes.SHA1),
        "sha224": (hashlib.sha224, hashes.SHA224),
        "sha256": (hashlib.sha256, hashes.SHA256),
        "sha384": (hashlib.sha384, hashes.SHA384),
        "sha512": (hashlib.sha512, hashes.SHA512),
    }

    if fragment not in mapping:
        raise XAdESError(f"Algoritmo de hash no soportado: {algorithm_uri}")

    return mapping[fragment]


class SRIXAdESFirmador:
    """Firmador XAdES-BES sencillo respaldado por la librería endesive.

    Permite pasar `empresa` explícita para evitar depender solo del thread-local.
    """

    def __init__(self, empresa=None):
        tenant = empresa or get_current_tenant()
        # Búsqueda priorizando empresa explícita
        base_qs = Opciones._base_manager
        self.opciones = None
        missing_parts = []
        if tenant:
            # Obtener registro aunque le falten campos para explicar bien
            registro = base_qs.filter(empresa=tenant).first()
            if not registro:
                raise XAdESError(
                    f"No existe registro de configuración (Opciones) para la empresa id={tenant.id}. Debe abrir Configuración > Firma Electrónica y guardar los datos."
                )
            # Revisar archivo
            if not registro.firma_electronica:
                missing_parts.append("archivo de firma (.p12/.pfx)")
            if not registro.password_firma:
                missing_parts.append("contraseña de la firma")
            if missing_parts:
                detalle = ", ".join(missing_parts)
                raise XAdESError(
                    f"Configuración incompleta para empresa id={tenant.id}: faltan {detalle}. Suba el archivo y contraseña y vuelva a intentar."
                )
            self.opciones = registro
        else:
            raise XAdESError("No se pudo determinar la empresa (tenant) actual para seleccionar la firma.")

    def firmar_xml_xades_bes(self, xml_path: str, xml_firmado_path: str) -> bool:
        """Firma un XML usando XAdES-BES y guarda el resultado."""
        return firmar_xml_con_endesive(
            xml_path,
            xml_firmado_path,
            opciones=self.opciones,
        )


def firmar_xml_xades_bes(xml_path: str, xml_firmado_path: str, empresa=None) -> bool:
    """Función de conveniencia para firmar un XML con XAdES-BES.

    Args:
        xml_path: ruta origen
        xml_firmado_path: ruta destino
        empresa: instancia Empresa (opcional)
    """
    firmador = SRIXAdESFirmador(empresa=empresa)
    return firmador.firmar_xml_xades_bes(xml_path, xml_firmado_path)


def firmar_xml_con_endesive(
    xml_path: str,
    xml_firmado_path: str,
    opciones=None,
    empresa=None,
) -> bool:
    """Firma XML usando la implementación XAdES de la librería endesive.

    Args:
        xml_path: ruta origen del XML.
        xml_firmado_path: ruta destino del XML firmado.
        opciones: instancia de ``Opciones`` ya resuelta (opcional).
        empresa: empresa explícita a usar si no se proporciona ``opciones``.

    Usa ``endesive.xades.BES.enveloped`` con una función de firmado basada en
    la llave privada del archivo PKCS#12 configurado en ``Opciones``.
    """
    try:
        # API actual de endesive (no existe endesive.xml.xades en versiones recientes)
        from endesive.xades import BES
    except ImportError as e:
        msg = (
            "Librería endesive no disponible. "
            "Instale con `pip install endesive>=2.17.0`"
        )
        logger.error("%s: %s", msg, e)
        raise XAdESError(msg)

    if opciones is None:
        signer_aux = SRIXAdESFirmador(empresa=empresa)
        opciones = signer_aux.opciones

    # Leer XML fuente
    xml_data = storage_read_bytes(xml_path)

    # Asegurar que el nodo raíz exponga Id="…" además de id="…" para el SRI
    try:
        doc = etree.parse(io.BytesIO(xml_data))
        root = doc.getroot()

        id_lower = root.get("id")
        id_value = id_lower or root.get("Id") or "comprobante"

        # Alinear ambos atributos usando el valor elegido
        root.set("Id", id_value)
        if id_lower != id_value:
            root.set("id", id_value)

        xml_data = etree.tostring(
            doc,
            encoding="UTF-8",
            xml_declaration=True,
            standalone=False,
        )
    except Exception as e:
        logger.warning("No se pudo preparar Id=comprobante en raíz: %s", e)

    # Cargar PKCS#12 (p12/pfx)
    try:
        with opciones.firma_electronica.open("rb") as pf:
            p12_bytes = pf.read()
        private_key, certificate, addl = pkcs12.load_key_and_certificates(
            p12_bytes, (opciones.password_firma or "").encode("utf-8")
        )
        if not private_key or not certificate:
            raise ValueError("No se pudo extraer llave o certificado del PKCS#12")
    except Exception as e:
        logger.error("Error leyendo PKCS#12: %s", e)
        raise XAdESError(f"Certificado PKCS#12 inválido: {e}")

    # Serializar certificado a DER
    try:
        cert_der = certificate.public_bytes(Encoding.DER)
    except Exception as e:
        logger.error("Error serializando certificado: %s", e)
        raise XAdESError(f"Error con certificado: {e}")

    # Función de firma para endesive (RSA + SHA256)
    def signproc(data: bytes, algo: str) -> bytes:
        try:
            _, hash_cls = resolver_hash_algoritmo(algo)
            return private_key.sign(data, padding.PKCS1v15(), hash_cls())
        except Exception as se:
            logger.error("Error firmando bytes canonizados: %s", se)
            raise

    # Construir XAdES-BES (enveloped)
    try:
        signer = BES()
        tree = signer.enveloped(
            xml_data,
            certificate,
            cert_der,
            signproc,
            tspurl=None,
            tspcred=None,
        )

        ns = {
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
            'xades': 'http://uri.etsi.org/01903/v1.3.2#'
        }
        signature_el = tree.find('.//ds:Signature', namespaces=ns)
        if signature_el is None:
            raise XAdESError("No se generó elemento ds:Signature en XML")

        signature_id = signature_el.get('Id') or f"Signature_{uuid.uuid4()}"
        signature_el.set('Id', signature_id)

        signed_info = signature_el.find('ds:SignedInfo', namespaces=ns)
        if signed_info is None:
            raise XAdESError("No se encontró ds:SignedInfo")

        ref = signed_info.find('ds:Reference', namespaces=ns)
        if ref is not None and ref.get('URI', '') == "":
            ref.set('URI', '#comprobante')

            # Recalcular digest tomando en cuenta los transforms declarados
            digest_value_el = ref.find('ds:DigestValue', namespaces=ns)
            if digest_value_el is None:
                raise XAdESError("No se encontró ds:DigestValue")

            digest_method_el = ref.find('ds:DigestMethod', namespaces=ns)
            if digest_method_el is None:
                raise XAdESError("No se encontró ds:DigestMethod")
            digest_algo_uri = digest_method_el.get('Algorithm')
            hashlib_fn, _ = resolver_hash_algoritmo(digest_algo_uri)

            target_root = tree.getroot()
            # Clonar el nodo para aplicar transforms sin mutar el original
            target_copy = deepcopy(target_root)

            transforms_el = ref.find('ds:Transforms', namespaces=ns)
            exclusive_c14n = False
            if transforms_el is not None:
                for transform in transforms_el.findall('ds:Transform', namespaces=ns):
                    algo = transform.get('Algorithm') or ''
                    if algo.endswith('#enveloped-signature'):
                        sig_inside = target_copy.find('.//ds:Signature', namespaces=ns)
                        if sig_inside is not None and sig_inside.getparent() is not None:
                            sig_inside.getparent().remove(sig_inside)
                    elif algo.endswith('xml-exc-c14n#'):
                        exclusive_c14n = True
                    elif algo.endswith('REC-xml-c14n-20010315'):
                        exclusive_c14n = False

            digest_buffer = io.BytesIO()
            etree.ElementTree(target_copy).write_c14n(
                digest_buffer,
                exclusive=exclusive_c14n,
                with_comments=False,
            )
            digest_raw = digest_buffer.getvalue()
            digest_b64 = base64.b64encode(hashlib_fn(digest_raw).digest()).decode()
            digest_value_el.text = digest_b64

            # Canonicalizar SignedInfo según el algoritmo declarado
            can_method = signed_info.find('ds:CanonicalizationMethod', namespaces=ns)
            can_algo = (can_method.get('Algorithm') if can_method is not None else '') or ''
            signed_info_buffer = io.BytesIO()
            etree.ElementTree(signed_info).write_c14n(
                signed_info_buffer,
                exclusive=can_algo.endswith('xml-exc-c14n#'),
                with_comments=can_algo.endswith('#WithComments'),
            )
            c14n_signed_info = signed_info_buffer.getvalue()

            # Firmar nuevamente SignedInfo con la URI ajustada
            signature_method_el = signed_info.find('ds:SignatureMethod', namespaces=ns)
            if signature_method_el is None:
                raise XAdESError("No se encontró ds:SignatureMethod")
            signature_algo_uri = signature_method_el.get('Algorithm')
            _, hash_cls = resolver_hash_algoritmo(signature_algo_uri)

            sig_bytes = private_key.sign(c14n_signed_info, padding.PKCS1v15(), hash_cls())
            sig_b64 = base64.b64encode(sig_bytes).decode()
            # Formatear en líneas de 64 caracteres como realiza endesive
            formatted = "\n".join(sig_b64[i:i + 64] for i in range(0, len(sig_b64), 64))
            sig_value_el = signature_el.find('ds:SignatureValue', namespaces=ns)
            if sig_value_el is None:
                raise XAdESError("No se encontró ds:SignatureValue")
            sig_value_el.text = formatted

        signed_bytes = etree.tostring(
            tree, encoding="UTF-8", xml_declaration=True, standalone=False
        )
    except Exception as e:
        logger.error("Error con endesive: %s", e)
        raise XAdESError(f"Error en firma con endesive: {e}")

    # Guardar XML firmado
    storage_write_bytes(xml_firmado_path, signed_bytes)

    logger.info("XML firmado con endesive XAdES-BES: %s", xml_firmado_path)
    return True
