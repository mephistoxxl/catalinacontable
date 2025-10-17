#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de la nueva implementación XAdES-BES basada en xades-bes-sri-ec
"""

import os
import sys
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

# NO usar Django, probar directo
print("="*80)
print("TEST FIRMA XADES-BES (xades-bes-sri-ec)")
print("="*80)

from lxml import etree

def test_firma_simple():
    """Test básico sin Django"""
    print("="*80)
    print("🧪 TEST FIRMA XADES-BES (xades-bes-sri-ec)")
    print("="*80)
    
    # Importar directamente
    from inventario.sri.firmador_xades_sri_ec import firmar_xml_xades_bes
    
    # XML de prueba simple
    xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.0.0">
    <infoTributaria>
        <ambiente>1</ambiente>
        <tipoEmision>1</tipoEmision>
        <razonSocial>EMPRESA TEST</razonSocial>
        <ruc>2390054060001</ruc>
        <claveAcceso>1234567890123456789012345678901234567890123456789</claveAcceso>
        <codDoc>01</codDoc>
        <estab>001</estab>
        <ptoEmi>999</ptoEmi>
        <secuencial>000000001</secuencial>
        <dirMatriz>DIRECCION TEST</dirMatriz>
    </infoTributaria>
    <infoFactura>
        <fechaEmision>17/10/2025</fechaEmision>
        <totalSinImpuestos>100.00</totalSinImpuestos>
        <totalDescuento>0.00</totalDescuento>
        <propina>0.00</propina>
        <importeTotal>112.00</importeTotal>
    </infoFactura>
</factura>"""
    
    # Guardar XML temporal
    xml_path = "test_factura.xml"
    with open(xml_path, 'wb') as f:
        f.write(xml_content)
    
    # Ruta del certificado
    cert_path = r"C:\Users\CORE I7\Desktop\catalinafact\firmas_secure\firmas\1713959011.p12"
    password = "Michelena24"
    xml_firmado_path = "test_factura_firmada.xml"
    
    print(f"\n📄 XML: {xml_path}")
    print(f"🔐 Certificado: {cert_path}")
    print(f"💾 Salida: {xml_firmado_path}")
    
    # Firmar
    print("\n🔐 Iniciando firma...")
    resultado = firmar_xml_xades_bes(xml_path, cert_path, password, xml_firmado_path)
    
    if resultado:
        print("\n✅ FIRMA EXITOSA!")
        
        # Verificar estructura
        with open(xml_firmado_path, 'rb') as f:
            xml_firmado = f.read()
        
        tree = etree.fromstring(xml_firmado)
        ns = {
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
            'etsi': 'http://uri.etsi.org/01903/v1.3.2#'
        }
        
        print("\n🔍 VERIFICANDO ESTRUCTURA:")
        
        # Signature
        sig = tree.find('.//ds:Signature', ns)
        if sig is not None:
            print(f"   ✅ Signature - Id: {sig.get('Id')}")
        
        # Object con Id
        obj = sig.find('ds:Object', ns) if sig is not None else None
        if obj is not None:
            obj_id = obj.get('Id')
            if obj_id:
                print(f"   ✅ Object - Id: {obj_id} (CRÍTICO PARA SRI)")
            else:
                print(f"   ❌ Object sin Id")
        
        # KeyInfo
        key_info = sig.find('.//ds:KeyInfo', ns) if sig is not None else None
        if key_info is not None:
            print(f"   ✅ KeyInfo - Id: {key_info.get('Id')}")
            
            # Verificar KeyValue
            key_value = key_info.find('ds:KeyValue', ns)
            if key_value is not None:
                print(f"   ✅ KeyValue presente (con RSA)")
            else:
                print(f"   ❌ KeyValue faltante")
        
        # SignedInfo
        signed_info = sig.find('ds:SignedInfo', ns) if sig is not None else None
        if signed_info is not None:
            refs = signed_info.findall('ds:Reference', ns)
            print(f"   ✅ SignedInfo con {len(refs)} referencias")
            
            for i, ref in enumerate(refs, 1):
                uri = ref.get('URI', '')
                transforms = ref.findall('.//ds:Transform', ns)
                print(f"      Ref {i}: {uri} ({len(transforms)} transforms)")
        
        # SignedProperties
        signed_props = tree.find('.//etsi:SignedProperties', ns)
        if signed_props is not None:
            signing_time = signed_props.find('.//etsi:SigningTime', ns)
            if signing_time is not None:
                print(f"   ✅ SigningTime: {signing_time.text}")
        
        print("\n" + "="*80)
        print("🎉 TEST COMPLETADO EXITOSAMENTE")
        print("="*80)
        print("\n📝 SIGUIENTE PASO:")
        print("   1. Firma una factura real desde la aplicación web")
        print("   2. Envía al SRI y verifica si Error 39 desaparece")
        
    else:
        print("\n❌ ERROR EN LA FIRMA")
        return False
    
    # Limpiar archivos de prueba
    try:
        os.remove(xml_path)
        os.remove(xml_firmado_path)
        print("\n🧹 Archivos de prueba eliminados")
    except:
        pass
    
    return True


if __name__ == "__main__":
    try:
        test_firma_simple()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
