#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para reproducir el bug de canonicalización."""

import io
from lxml import etree

# XML de prueba simple
xml_test = b'''<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.1.0">
  <infoTributaria>
    <ambiente>1</ambiente>
  </infoTributaria>
  <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
    <ds:SignedInfo>
      <ds:Reference URI="#comprobante">
        <ds:Transforms>
          <ds:Transform Algorithm="http://www.w3.org/TR/1999/REC-xpath-19991116">
            <ds:XPath>not(ancestor-or-self::ds:Signature)</ds:XPath>
          </ds:Transform>
        </ds:Transforms>
      </ds:Reference>
    </ds:SignedInfo>
  </ds:Signature>
</factura>'''

print("=" * 80)
print("PRUEBA 1: Canonicalización directa del árbol original")
print("=" * 80)
tree = etree.parse(io.BytesIO(xml_test))
root = tree.getroot()

# Remover firma
sig = root.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature")
if sig is not None:
    root.remove(sig)

# Método 1: tostring con c14n
result1 = etree.tostring(root, method="c14n")
print(f"\nMétodo 1 (tostring c14n): {result1[:100]}")

print("\n" + "=" * 80)
print("PRUEBA 2: Serializar y re-parsear (como hacemos en el código)")
print("=" * 80)

# Recargar XML
tree = etree.parse(io.BytesIO(xml_test))
root = tree.getroot()

# Serializar y re-parsear (como en _canonicalizar_objetivo)
xml_bytes = etree.tostring(root, encoding="UTF-8", method="xml")
target = etree.fromstring(xml_bytes)

# Remover firma
sig = target.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature")
if sig is not None:
    target.remove(sig)

# Método 2: tostring con c14n en elemento re-parseado
result2 = etree.tostring(target, method="c14n")
print(f"\nMétodo 2 (fromstring + tostring c14n): {result2[:100]}")

print("\n" + "=" * 80)
print("PRUEBA 3: ElementTree + write_c14n (método anterior)")
print("=" * 80)

# Recargar XML
tree = etree.parse(io.BytesIO(xml_test))
root = tree.getroot()

# Serializar y re-parsear
xml_bytes = etree.tostring(root, encoding="UTF-8", method="xml")
target = etree.fromstring(xml_bytes)

# Remover firma
sig = target.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature")
if sig is not None:
    target.remove(sig)

# Método 3: ElementTree + write_c14n
buffer = io.BytesIO()
etree.ElementTree(target).write_c14n(buffer)
result3 = buffer.getvalue()
print(f"\nMétodo 3 (ElementTree + write_c14n): {result3[:100]}")

print("\n" + "=" * 80)
print("COMPARACIÓN")
print("=" * 80)
print(f"Método 1 == Método 2: {result1 == result2}")
print(f"Método 1 == Método 3: {result1 == result3}")
print(f"Método 2 == Método 3: {result2 == result3}")

# Verificar duplicaciones
if b'id="comprobante""' in result2:
    print("\n⚠️ DUPLICACIÓN DETECTADA en Método 2!")
if b'id="comprobante""' in result3:
    print("\n⚠️ DUPLICACIÓN DETECTADA en Método 3!")
