# -*- coding: utf-8 -*-
"""Test simple de firma XAdES-BES"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from inventario.sri.firmador_xades_sri_ec import firmar_xml_xades_bes
from lxml import etree

print("="*80)
print("TEST FIRMA XADES-BES")
print("="*80)

# XML de prueba
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
xml_path = "test_xml.xml"
with open(xml_path, 'wb') as f:
    f.write(xml_content)

# Configuración
cert_path = r"C:\Users\CORE I7\Desktop\catalinafact\firmas_secure\firmas\GERENTE_GENERAL_ANDREA_MERCEDES_MICHELENA_PUMALPA_1750848333-200224145545.p12"
password = "Michelena24"
output_path = "test_xml_firmado.xml"

print(f"\nXML: {xml_path}")
print(f"Cert: {cert_path}")
print(f"Salida: {output_path}")
print("\nFirmando...")

# Firmar
try:
    resultado = firmar_xml_xades_bes(xml_path, cert_path, password, output_path)
    
    if resultado:
        print("\n[OK] FIRMA EXITOSA!")
        
        # Verificar
        with open(output_path, 'rb') as f:
            xml_firmado = f.read()
        
        tree = etree.fromstring(xml_firmado)
        ns = {
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
            'etsi': 'http://uri.etsi.org/01903/v1.3.2#'
        }
        
        print("\nEstructura verificada:")
        
        sig = tree.find('.//ds:Signature', ns)
        if sig is not None:
            print(f"  [OK] Signature Id: {sig.get('Id')}")
            
            obj = sig.find('ds:Object', ns)
            if obj is not None and obj.get('Id'):
                print(f"  [OK] Object Id: {obj.get('Id')} (CRITICO SRI)")
            
            key_info = sig.find('.//ds:KeyInfo', ns)
            if key_info is not None:
                print(f"  [OK] KeyInfo Id: {key_info.get('Id')}")
                
                key_value = key_info.find('ds:KeyValue', ns)
                if key_value is not None:
                    print(f"  [OK] KeyValue con RSA")
            
            signed_info = sig.find('ds:SignedInfo', ns)
            if signed_info is not None:
                refs = signed_info.findall('ds:Reference', ns)
                print(f"  [OK] {len(refs)} referencias en SignedInfo")
        
        print("\n" + "="*80)
        print("PRUEBA COMPLETADA")
        print("="*80)
        print("\nProximo paso:")
        print("1. Firma una factura real desde la aplicacion web")
        print("2. Envia al SRI y verifica si Error 39 desaparece")
        
    else:
        print("\n[ERROR] Firma fallida")
        
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()

# Limpiar
import os
try:
    os.remove(xml_path)
    os.remove(output_path)
    print("\nArchivos de prueba eliminados")
except:
    pass
