#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar manualmente la SignatureValue
"""
import hashlib
import base64
from lxml import etree
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import os

# Leer el XML firmado
xml_path = r"C:\Users\CORE I7\Desktop\catalinafact\media\facturas\1713959011001\xml\factura_001-999-000000049_20251017_143718_firmado.xml"

with open(xml_path, 'rb') as f:
    tree = etree.parse(f)
    root = tree.getroot()

print("="*80)
print("VERIFICACIÓN MANUAL DE SIGNATUREVALUE")
print("="*80)

# Buscar SignedInfo
ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
signed_info = root.find(".//ds:SignedInfo", ns)

if signed_info is None:
    print("❌ No se encontró SignedInfo")
    exit(1)

# Canonicalizar SignedInfo
signed_info_c14n = etree.tostring(signed_info, method="c14n", exclusive=False, with_comments=False)

print(f"\n📊 SignedInfo canonicalizado ({len(signed_info_c14n)} bytes):")
print(signed_info_c14n.decode('utf-8')[:500])

# Calcular SHA1 de SignedInfo
signed_info_sha1 = hashlib.sha1(signed_info_c14n).digest()
print(f"\n🔐 SHA1 de SignedInfo: {base64.b64encode(signed_info_sha1).decode()}")

# Extraer SignatureValue del XML
sig_value_elem = root.find(".//ds:SignatureValue", ns)
if sig_value_elem is not None:
    sig_value_b64 = sig_value_elem.text.replace('\n', '').replace(' ', '')
    sig_value_bytes = base64.b64decode(sig_value_b64)
    print(f"\n📝 SignatureValue del XML: {len(sig_value_bytes)} bytes")
    print(f"   Primeros 20 bytes: {sig_value_bytes[:20].hex()}")
else:
    print("\n❌ No se encontró SignatureValue")

# Intentar verificar la firma con el certificado
cert_elem = root.find(".//ds:X509Certificate", ns)
if cert_elem is not None:
    from cryptography import x509
    cert_der = base64.b64decode(cert_elem.text)
    cert = x509.load_der_x509_certificate(cert_der, default_backend())
    public_key = cert.public_key()
    
    print(f"\n📜 Certificado cargado: {cert.subject.rfc4514_string()}")
    
    try:
        # Verificar con PKCS1v15 (RSA-SHA1)
        from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
        public_key.verify(
            sig_value_bytes,
            signed_info_c14n,
            asym_padding.PKCS1v15(),
            hashes.SHA1()
        )
        print("✅ ¡FIRMA VÁLIDA! La SignatureValue es correcta")
    except Exception as e:
        print(f"❌ FIRMA INVÁLIDA: {e}")
else:
    print("\n❌ No se encontró certificado en XML")

print("\n" + "="*80)
