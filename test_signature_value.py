from lxml import etree
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import base64

# Cargar el XML firmado
xml_path = r"media\facturas\2390054060001\xml\factura_001-999-000000016_20251017_161628_firmado.xml"

with open(xml_path, 'rb') as f:
    doc = etree.parse(f)

root = doc.getroot()
ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}

print("=" * 80)
print("VERIFICACIÓN DE FIRMA RSA")
print("=" * 80)

# 1. Obtener SignedInfo
signed_info = root.find('.//ds:SignedInfo', ns)
if signed_info is None:
    print("❌ No se encontró SignedInfo")
    exit(1)

# 2. Canonicalizar SignedInfo (Inclusive C14N)
signed_info_c14n = etree.tostring(signed_info, method='c14n', exclusive=False, with_comments=False)

print(f"\n📊 SignedInfo canonicalizado: {len(signed_info_c14n)} bytes")
print(f"📊 Primeros 200 bytes:")
print(signed_info_c14n[:200])

# 3. Obtener SignatureValue
sig_value_elem = root.find('.//ds:SignatureValue', ns)
if sig_value_elem is None:
    print("❌ No se encontró SignatureValue")
    exit(1)

signature_b64 = sig_value_elem.text.strip().replace('\n', '').replace(' ', '')
signature_bytes = base64.b64decode(signature_b64)

print(f"\n📊 Firma: {len(signature_bytes)} bytes")
print(f"📊 Primeros 20 bytes (hex): {signature_bytes[:20].hex()}")

# 4. Obtener certificado
cert_elem = root.find('.//ds:X509Certificate', ns)
if cert_elem is None:
    print("❌ No se encontró certificado")
    exit(1)

cert_b64 = cert_elem.text.strip().replace('\n', '').replace(' ', '')
cert_der = base64.b64decode(cert_b64)
certificate = x509.load_der_x509_certificate(cert_der, default_backend())

print(f"\n📊 Certificado:")
print(f"   Subject: {certificate.subject.rfc4514_string()}")

# 5. Verificar firma
public_key = certificate.public_key()

try:
    public_key.verify(
        signature_bytes,
        signed_info_c14n,
        padding.PKCS1v15(),
        hashes.SHA1()
    )
    print(f"\n✅✅✅ FIRMA VÁLIDA ✅✅✅")
    print("La firma RSA-SHA1 es correcta y coincide con el SignedInfo")
except Exception as e:
    print(f"\n❌❌❌ FIRMA INVÁLIDA ❌❌❌")
    print(f"Error: {str(e)}")
    print("\nPosibles causas:")
    print("1. SignedInfo modificado después de firmar")
    print("2. Certificado no coincide con la clave privada usada")
    print("3. Algoritmo de firma incorrecto")

print("\n" + "=" * 80)
