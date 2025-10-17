#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar manualmente el digest SHA1 de la factura
"""
import hashlib
import base64
from lxml import etree

# Leer el XML firmado
xml_path = r"C:\Users\CORE I7\Desktop\catalinafact\media\facturas\1713959011001\xml\factura_001-999-000000049_20251017_143718_firmado.xml"

with open(xml_path, 'rb') as f:
    tree = etree.parse(f)
    root = tree.getroot()

print("="*80)
print("VERIFICACIÓN MANUAL DE DIGEST SHA1")
print("="*80)

# Remover el Signature
sig = root.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature")
if sig is not None:
    root.remove(sig)
    print("✅ Signature removido")
else:
    print("⚠️ No se encontró Signature")

# Canonicalizar
canonical = etree.tostring(root, method="c14n", exclusive=False, with_comments=False)

print(f"\n📊 Longitud canonical: {len(canonical)} bytes")
print(f"📄 Primeros 300 bytes:")
print(canonical[:300])
print(f"\n📄 Últimos 300 bytes:")
print(canonical[-300:])

# Calcular digest SHA1
digest_bytes = hashlib.sha1(canonical).digest()
digest_b64 = base64.b64encode(digest_bytes).decode('ascii')

print(f"\n🔐 Digest SHA1 calculado: {digest_b64}")
print(f"📋 Digest en XML:         qpr+tjI6zz6iZJ8he+iRwvcpEjA=")

if digest_b64 == "qpr+tjI6zz6iZJ8he+iRwvcpEjA=":
    print("\n✅ ¡MATCH! El digest coincide")
else:
    print("\n❌ NO MATCH - Los digests difieren")
    
    # Comparar byte por byte
    expected = "qpr+tjI6zz6iZJ8he+iRwvcpEjA="
    print(f"\nComparación carácter por carácter:")
    for i, (c1, c2) in enumerate(zip(digest_b64, expected)):
        if c1 != c2:
            print(f"  Posición {i}: '{c1}' != '{c2}'")

print("\n" + "="*80)
