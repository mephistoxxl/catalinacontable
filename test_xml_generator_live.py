#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test en vivo para verificar qué módulo usa xml_generator
"""
import os
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
import django
django.setup()

print("="*80)
print("VERIFICACIÓN EN VIVO")
print("="*80)

# Importar el generador
from inventario.sri import xml_generator

# Ver qué ET está usando
ET_module = str(type(xml_generator.ET))
print(f"\nxml_generator.ET = {ET_module}")

if 'lxml' in ET_module:
    print("✅ xml_generator usa lxml.etree")
else:
    print(f"❌ xml_generator usa {ET_module}")
    print("   NECESITA USAR lxml.etree")

# Verificar el módulo directamente
print(f"\nMódulo real: {xml_generator.ET.__module__}")

# Test de encoding
try:
    root = xml_generator.ET.Element('test')
    root.text = 'TELÉFONO'
    xml_bytes = xml_generator.ET.tostring(root, encoding='utf-8')
    
    if b'\xc3\x89' in xml_bytes:
        print("✅ UTF-8 correcto: É = \\xc3\\x89")
    elif b'\xc9' in xml_bytes:
        print("❌ UTF-8 INCORRECTO: É = \\xc9")
    else:
        print("⚠️  No se encontró É")
        
except Exception as e:
    print(f"❌ Error en test: {e}")

print("\n" + "="*80)
