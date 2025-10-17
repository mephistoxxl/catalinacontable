#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar la validez del certificado
"""
import base64
from lxml import etree
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timezone

# Leer el XML firmado
xml_path = r"C:\Users\CORE I7\Desktop\catalinafact\media\facturas\1713959011001\xml\factura_001-999-000000049_20251017_143718_firmado.xml"

with open(xml_path, 'rb') as f:
    tree = etree.parse(f)
    root = tree.getroot()

print("="*80)
print("VERIFICACIÓN DE CERTIFICADO")
print("="*80)

ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
cert_elem = root.find(".//ds:X509Certificate", ns)

if cert_elem is None:
    print("❌ No se encontró certificado")
    exit(1)

cert_der = base64.b64decode(cert_elem.text)
cert = x509.load_der_x509_certificate(cert_der, default_backend())

print(f"\n📜 Subject: {cert.subject.rfc4514_string()}")
print(f"📜 Issuer: {cert.issuer.rfc4514_string()}")
print(f"\n⏰ Válido desde: {cert.not_valid_before_utc}")
print(f"⏰ Válido hasta: {cert.not_valid_after_utc}")

# Verificar validez temporal
now = datetime.now(timezone.utc)
print(f"\n🕐 Fecha actual: {now}")

if now < cert.not_valid_before_utc:
    print("❌ CERTIFICADO AÚN NO VÁLIDO")
elif now > cert.not_valid_after_utc:
    print("❌ CERTIFICADO EXPIRADO")
else:
    print("✅ Certificado temporalmente válido")
    days_remaining = (cert.not_valid_after_utc - now).days
    print(f"   Quedan {days_remaining} días de validez")

# Verificar SigningTime del XML
from lxml import etree
xades_ns = {'xades': 'http://uri.etsi.org/01903/v1.3.2#'}
signing_time_elem = root.find(".//xades:SigningTime", xades_ns)

if signing_time_elem is not None:
    signing_time_str = signing_time_elem.text
    print(f"\n🕐 SigningTime del XML: {signing_time_str}")
    
    # Parsear y verificar
    from dateutil import parser as date_parser
    try:
        signing_time = date_parser.parse(signing_time_str)
        if signing_time < cert.not_valid_before_utc:
            print("❌ Firma generada ANTES de validez del certificado")
        elif signing_time > cert.not_valid_after_utc:
            print("❌ Firma generada DESPUÉS de validez del certificado")
        else:
            print("✅ SigningTime dentro del periodo de validez del certificado")
    except Exception as e:
        print(f"⚠️ Error parseando SigningTime: {e}")

# Verificar Serial Number
print(f"\n🔢 Serial Number: {cert.serial_number}")

# Verificar Key Usage
try:
    key_usage = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.KEY_USAGE)
    print(f"\n🔑 Key Usage:")
    print(f"   - Digital Signature: {key_usage.value.digital_signature}")
    print(f"   - Non Repudiation: {key_usage.value.content_commitment}")
except:
    print("\n⚠️ No se encontró extensión Key Usage")

print("\n" + "="*80)
