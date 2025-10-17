#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar la estructura XAdES con Exclusive C14N
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, r"C:\Users\CORE I7\Desktop\catalinafact")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sistema.settings")
django.setup()

from lxml import etree

print("="*80)
print("VERIFICACIÓN DE ESTRUCTURA XADES CON EXCLUSIVE C14N")
print("="*80)

# Buscar el XML firmado más reciente
import glob
xml_pattern = r"C:\Users\CORE I7\Desktop\catalinafact\media\facturas\*\xml\*_firmado.xml"
xmls = glob.glob(xml_pattern, recursive=True)

if not xmls:
    print("❌ No se encontraron XMLs firmados")
    sys.exit(1)

# Ordenar por fecha de modificación
xmls.sort(key=os.path.getmtime, reverse=True)
xml_path = xmls[0]

print(f"\n📄 Analizando: {os.path.basename(xml_path)}")

with open(xml_path, 'rb') as f:
    tree = etree.parse(f)
    root = tree.getroot()

ns = {
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
    'xades': 'http://uri.etsi.org/01903/v1.3.2#'
}

# Verificar algoritmo de canonicalización
c14n_method = root.find('.//ds:CanonicalizationMethod', ns)
if c14n_method is not None:
    c14n_algo = c14n_method.get('Algorithm')
    print(f"\n🔧 Canonicalization Algorithm: {c14n_algo}")
    if "xml-exc-c14n" in c14n_algo:
        print("   ✅ Usando Exclusive C14N (correcto para SRI)")
    else:
        print(f"   ❌ Usando {c14n_algo} (debería ser Exclusive C14N)")
else:
    print("\n❌ No se encontró CanonicalizationMethod")

# Verificar transforms en Reference
references = root.findall('.//ds:Reference', ns)
print(f"\n📋 Referencias encontradas: {len(references)}")

for i, ref in enumerate(references, 1):
    uri = ref.get('URI', '')
    print(f"\n   Reference {i}: URI={uri}")
    
    transforms = ref.findall('.//ds:Transform', ns)
    print(f"   Transforms: {len(transforms)}")
    
    for j, transform in enumerate(transforms, 1):
        algo = transform.get('Algorithm')
        if "enveloped-signature" in algo:
            print(f"      {j}. ✅ Enveloped Signature")
        elif "xml-exc-c14n" in algo:
            print(f"      {j}. ✅ Exclusive C14N")
        elif "xpath" in algo.lower():
            print(f"      {j}. ⚠️ XPath transform (SRI prefiere enveloped-signature)")
        else:
            print(f"      {j}. {algo}")

# Verificar SignatureMethod
sig_method = root.find('.//ds:SignatureMethod', ns)
if sig_method is not None:
    sig_algo = sig_method.get('Algorithm')
    print(f"\n🔐 Signature Algorithm: {sig_algo}")
    if "rsa-sha1" in sig_algo:
        print("   ✅ RSA-SHA1 (correcto)")
    else:
        print(f"   ❌ {sig_algo} (debería ser RSA-SHA1)")
else:
    print("\n❌ No se encontró SignatureMethod")

# Verificar DigestMethod
digest_methods = root.findall('.//ds:DigestMethod', ns)
print(f"\n📊 Digest Methods: {len(digest_methods)}")
all_sha1 = True
for dm in digest_methods:
    algo = dm.get('Algorithm')
    if "sha1" not in algo.lower():
        print(f"   ❌ {algo} (debería ser SHA1)")
        all_sha1 = False

if all_sha1:
    print("   ✅ Todos usan SHA1 (correcto)")

print("\n" + "="*80)
print("\n🚀 Ahora intenta enviar esta factura al SRI para validar.")
print("   Si aún da Error 39, comparte el log completo de la respuesta del SRI.")
print("="*80)
