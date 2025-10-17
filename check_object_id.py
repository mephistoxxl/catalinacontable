#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script simple para verificar que Object tenga Id en un XML ya firmado
"""

from lxml import etree

# Usar el XML más reciente firmado
XML_PATH = r"C:\Users\CORE I7\Desktop\catalinafact\media\facturas\2390054060001\xml\factura_001-999-000000017_20251017_163437_firmado.xml"

print("="*80)
print("VERIFICANDO ATRIBUTO Id EN <ds:Object>")
print("="*80)
print(f"\nAnalizando: {XML_PATH}")

tree = etree.parse(XML_PATH)
root = tree.getroot()

ns = {
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
    'xades': 'http://uri.etsi.org/01903/v1.3.2#'
}

# Buscar Signature
signature = root.find('.//ds:Signature', ns)
if signature:
    sig_id = signature.get('Id', 'N/A')
    print(f"\n✅ Signature encontrada - Id: {sig_id}")
    
    # Buscar Object
    obj = signature.find('ds:Object', ns)
    if obj is not None:
        object_id = obj.get('Id')
        
        print(f"\n📦 Elemento <ds:Object>:")
        if object_id:
            print(f"   ✅ TIENE Id: {object_id}")
            print("\n🎯 ¡PERFECTO! Object tiene atributo Id")
        else:
            print(f"   ❌ NO TIENE Id")
            print("\n⚠️  Falta el atributo Id en Object")
            print("   (Este XML fue firmado con código antiguo)")
    else:
        print("\n❌ No se encontró elemento Object")
else:
    print("\n❌ No se encontró Signature")

print("\n" + "="*80)
print("NOTA: Para verificar el cambio, firma una nueva factura después")
print("      de haber limpiado el caché de Python.")
print("="*80)
