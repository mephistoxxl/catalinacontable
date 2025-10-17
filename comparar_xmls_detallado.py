#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para comparar en detalle el XML autorizado en producción vs nuestro XML
"""

from lxml import etree
import base64

# Archivos a comparar
XML_AUTORIZADO = r"C:\Users\CORE I7\Desktop\catalinafact\xml_autorizado_produccion.xml"
XML_NUESTRO = r"C:\Users\CORE I7\Desktop\catalinafact\media\facturas\2390054060001\xml\factura_001-999-000000017_20251017_163437_firmado.xml"

def analizar_signature(xml_path, nombre):
    """Analiza la estructura de la firma en detalle"""
    print(f"\n{'='*80}")
    print(f"ANALIZANDO: {nombre}")
    print(f"{'='*80}")
    
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    # Namespaces
    ns = {
        'ds': 'http://www.w3.org/2000/09/xmldsig#',
        'etsi': 'http://uri.etsi.org/01903/v1.3.2#'
    }
    
    signature = root.find('.//ds:Signature', ns)
    if signature is None:
        print("❌ NO SE ENCONTRÓ SIGNATURE")
        return
    
    print(f"\n📋 Signature Id: {signature.get('Id')}")
    
    # SignedInfo
    signed_info = signature.find('ds:SignedInfo', ns)
    if signed_info:
        print("\n🔍 SignedInfo:")
        
        # CanonicalizationMethod
        c14n = signed_info.find('ds:CanonicalizationMethod', ns)
        print(f"   - C14N: {c14n.get('Algorithm')}")
        
        # SignatureMethod
        sig_method = signed_info.find('ds:SignatureMethod', ns)
        print(f"   - Signature Method: {sig_method.get('Algorithm')}")
        
        # References
        references = signed_info.findall('ds:Reference', ns)
        print(f"\n   📌 Referencias ({len(references)}):")
        
        for i, ref in enumerate(references, 1):
            print(f"\n   Referencia {i}:")
            print(f"      - Id: {ref.get('Id')}")
            print(f"      - URI: {ref.get('URI')}")
            print(f"      - Type: {ref.get('Type')}")
            
            # Transforms
            transforms = ref.findall('.//ds:Transform', ns)
            if transforms:
                print(f"      - Transforms ({len(transforms)}):")
                for t in transforms:
                    print(f"         * {t.get('Algorithm')}")
            else:
                print(f"      - Transforms: NINGUNO")
            
            # Digest
            digest_method = ref.find('ds:DigestMethod', ns)
            digest_value = ref.find('ds:DigestValue', ns)
            print(f"      - Digest Method: {digest_method.get('Algorithm')}")
            print(f"      - Digest Value: {digest_value.text}")
    
    # KeyInfo
    key_info = signature.find('ds:KeyInfo', ns)
    if key_info:
        print(f"\n🔑 KeyInfo:")
        print(f"   - Id: {key_info.get('Id')}")
        
        # Verificar orden de hijos
        print(f"\n   📦 Elementos hijos en orden:")
        for i, child in enumerate(key_info, 1):
            tag = child.tag.replace('{http://www.w3.org/2000/09/xmldsig#}', 'ds:')
            print(f"      {i}. {tag}")
            
            # Si es KeyValue, mostrar contenido
            if 'KeyValue' in child.tag:
                rsa = child.find('ds:RSAKeyValue', ns)
                if rsa:
                    modulus = rsa.find('ds:Modulus', ns)
                    exponent = rsa.find('ds:Exponent', ns)
                    print(f"         - Modulus: {modulus.text[:50]}...")
                    print(f"         - Exponent: {exponent.text}")
    
    # Object / SignedProperties
    obj = signature.find('ds:Object', ns)
    if obj:
        print(f"\n📦 Object:")
        print(f"   - Id: {obj.get('Id')}")
        
        qual_props = obj.find('etsi:QualifyingProperties', ns)
        if qual_props:
            print(f"   - QualifyingProperties Target: {qual_props.get('Target')}")
            
            signed_props = qual_props.find('etsi:SignedProperties', ns)
            if signed_props:
                print(f"   - SignedProperties Id: {signed_props.get('Id')}")
                
                # SigningTime
                signing_time = signed_props.find('.//etsi:SigningTime', ns)
                if signing_time is not None:
                    print(f"   - SigningTime: {signing_time.text}")
                
                # Certificate digest
                cert_digest = signed_props.find('.//etsi:CertDigest/ds:DigestValue', ns)
                if cert_digest is not None:
                    print(f"   - Cert Digest: {cert_digest.text}")

def comparar_certificados(xml_path1, xml_path2):
    """Compara los certificados en ambos XMLs"""
    print(f"\n{'='*80}")
    print("COMPARANDO CERTIFICADOS")
    print(f"{'='*80}")
    
    ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
    
    tree1 = etree.parse(xml_path1)
    tree2 = etree.parse(xml_path2)
    
    cert1_elem = tree1.find('.//ds:X509Certificate', ns)
    cert2_elem = tree2.find('.//ds:X509Certificate', ns)
    
    if cert1_elem is not None and cert2_elem is not None:
        cert1 = cert1_elem.text.strip()
        cert2 = cert2_elem.text.strip()
        
        if cert1 == cert2:
            print("✅ Los certificados son IDÉNTICOS")
        else:
            print("❌ Los certificados son DIFERENTES")
            print(f"\nCertificado autorizado (primeros 100 chars):\n{cert1[:100]}...")
            print(f"\nCertificado nuestro (primeros 100 chars):\n{cert2[:100]}...")
    else:
        print("❌ No se pudieron extraer los certificados")

def main():
    print("🔬 COMPARACIÓN DETALLADA DE FIRMAS XML")
    print("="*80)
    
    # Analizar ambos XMLs
    analizar_signature(XML_AUTORIZADO, "XML AUTORIZADO EN PRODUCCIÓN")
    analizar_signature(XML_NUESTRO, "NUESTRO XML (RECHAZADO EN PRUEBAS)")
    
    # Comparar certificados
    comparar_certificados(XML_AUTORIZADO, XML_NUESTRO)
    
    print(f"\n{'='*80}")
    print("✅ COMPARACIÓN COMPLETADA")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
