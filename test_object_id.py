#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar que el Object tenga atributo Id después del cambio
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, r'C:\Users\CORE I7\Desktop\catalinafact')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from lxml import etree
from inventario.sri.firmador_xades_manual import firmar_xml_xades_bes_manual
from django.core.files.storage import default_storage
import tempfile

def verificar_object_id():
    """Verifica que el Object tenga Id"""
    
    # Crear un XML simple de prueba
    xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.0.0">
    <infoTributaria>
        <ambiente>1</ambiente>
        <tipoEmision>1</tipoEmision>
        <razonSocial>TEST</razonSocial>
        <ruc>2390054060001</ruc>
        <claveAcceso>1234567890123456789012345678901234567890123456789</claveAcceso>
        <codDoc>01</codDoc>
        <estab>001</estab>
        <ptoEmi>001</ptoEmi>
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
    
    # Guardar temporalmente
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as f:
        temp_xml = f.name
        f.write(xml_content)
    
    try:
        # Ruta del certificado de prueba
        cert_path = r"C:\Users\CORE I7\Desktop\catalinafact\firmas_secure\firmas\1713959011.p12"
        password = "Michelena24"
        
        output_path = temp_xml.replace('.xml', '_firmado.xml')
        
        print("🔐 Firmando XML de prueba...")
        resultado = firmar_xml_xades_bes_manual(temp_xml, cert_path, password, output_path)
        
        if resultado:
            print("✅ Firma exitosa!")
            
            # Leer y verificar
            with open(output_path, 'rb') as f:
                xml_firmado = f.read()
            
            tree = etree.fromstring(xml_firmado)
            ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
            
            # Buscar Object
            obj = tree.find('.//ds:Object', ns)
            
            if obj is not None:
                object_id = obj.get('Id')
                if object_id:
                    print(f"✅✅✅ OBJECT TIENE ID: {object_id}")
                    print("\n🎯 CAMBIO APLICADO CORRECTAMENTE")
                    return True
                else:
                    print("❌ Object NO tiene atributo Id")
                    return False
            else:
                print("❌ No se encontró elemento Object")
                return False
        else:
            print("❌ Error al firmar")
            return False
            
    finally:
        # Limpiar archivos temporales
        if os.path.exists(temp_xml):
            os.remove(temp_xml)
        output_path = temp_xml.replace('.xml', '_firmado.xml')
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == "__main__":
    print("="*80)
    print("VERIFICANDO ATRIBUTO Id EN <ds:Object>")
    print("="*80)
    verificar_object_id()
