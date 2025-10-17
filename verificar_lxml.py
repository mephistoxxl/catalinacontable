#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar que xml_generator.py está usando lxml correctamente
"""
import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("="*80)
print("VERIFICACIÓN DE MÓDULOS")
print("="*80)

# 1. Verificar que lxml está instalado
try:
    from lxml import etree
    print("✅ lxml instalado correctamente")
    print(f"   Versión: {etree.LXML_VERSION}")
except ImportError as e:
    print(f"❌ ERROR: lxml no está instalado: {e}")
    sys.exit(1)

# 2. Limpiar sys.modules si xml_generator ya está cargado
if 'inventario.sri.xml_generator' in sys.modules:
    print("⚠️  xml_generator ya estaba en memoria - eliminando cache...")
    del sys.modules['inventario.sri.xml_generator']

# 3. Importar xml_generator
try:
    from inventario.sri import xml_generator
    print("✅ xml_generator importado")
except ImportError as e:
    print(f"❌ ERROR importando xml_generator: {e}")
    sys.exit(1)

# 4. Verificar que está usando lxml
ET_module = xml_generator.ET.__name__
print(f"\n   xml_generator.ET = {ET_module}")

if 'lxml' in ET_module:
    print("✅ xml_generator está usando lxml.etree")
else:
    print(f"❌ ERROR: xml_generator está usando {ET_module}")
    print("   Debería ser 'lxml.etree'")
    sys.exit(1)

# 5. Test de encoding UTF-8
print("\n" + "="*80)
print("TEST DE ENCODING UTF-8")
print("="*80)

root = xml_generator.ET.Element('test')
root.text = 'TELÉFONO'
xml_bytes = xml_generator.ET.tostring(root, encoding='utf-8', xml_declaration=True)

print(f"Texto: {root.text}")
print(f"Bytes: {xml_bytes[:100]}")

# Verificar que É está codificado como \xc3\x89 (UTF-8 correcto)
if b'\xc3\x89' in xml_bytes:
    print("✅ UTF-8 correcto: É = \\xc3\\x89")
elif b'\xc9' in xml_bytes:
    print("❌ ERROR: É = \\xc9 (Latin-1/Windows-1252)")
    sys.exit(1)
else:
    print("⚠️  No se encontró É en el output")

# 6. Test de round-trip
loaded = xml_generator.ET.fromstring(xml_bytes)
if loaded.text == 'TELÉFONO':
    print("✅ Round-trip correcto: TELÉFONO → bytes → TELÉFONO")
else:
    print(f"❌ ERROR: Round-trip falló: {loaded.text}")
    sys.exit(1)

print("\n" + "="*80)
print("✅ TODOS LOS TESTS PASARON")
print("="*80)
print("\nEl servidor Django ahora debe generar XMLs con UTF-8 correcto.")
print("Crea una nueva factura y verifica el XML antes de firmar.")
