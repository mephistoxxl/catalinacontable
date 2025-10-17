#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Prueba simple de firma sin Django models
"""
import hashlib
import base64
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend

# Leer XML
xml_path = r"C:\Users\CORE I7\Desktop\catalinafact\media\facturas\1713959011001\xml\factura_001-999-000000049_20251017_143718.xml"
p12_path = r"C:\Users\CORE I7\Desktop\catalinafact\firmas_secure\firmas\1713959011.p12"
password = b"1713959011"

print("="*80)
print("PRUEBA SIMPLE DE ESTRUCTURA DE FIRMA")
print("="*80)

# Cargar P12
with open(p12_path, 'rb') as f:
    p12_data = f.read()

private_key, certificate, _ = pkcs12.load_key_and_certificates(
    p12_data, password, default_backend()
)

print(f"\nCertificado cargado: {certificate.subject.rfc4514_string()[:50]}...")

# Cargar XML
with open(xml_path, 'rb') as f:
    tree = etree.parse(f)
    root = tree.getroot()

print(f"XML cargado: {root.tag}")

# Simular estructura que debería tener
print("\n" + "="*80)
print("ESTRUCTURA QUE DEBERÍA GENERAR:")
print("="*80)

print("""
SignedInfo:
  - CanonicalizationMethod: http://www.w3.org/TR/2001/REC-xml-c14n-20010315
  - SignatureMethod: http://www.w3.org/2000/09/xmldsig#rsa-sha1
  
  - Reference 1 (Factura):
      URI: #comprobante
      Transforms:
        * enveloped-signature
      DigestMethod: SHA1
      DigestValue: <calculado>
  
  - Reference 2 (KeyInfo):
      URI: #Certificate<id>
      DigestMethod: SHA1
      DigestValue: <calculado del KeyInfo>
  
  - Reference 3 (SignedProperties):
      URI: #SignedProperties<id>
      Type: http://uri.etsi.org/01903#SignedProperties
      DigestMethod: SHA1
      DigestValue: <calculado>
      (SIN Transforms)
""")

print("="*80)
print("\nEsto coincide con facturas AUTORIZADAS del SRI")
print("="*80)
