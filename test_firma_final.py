# -*- coding: utf-8 -*-
"""
PRUEBA RAPIDA DE FIRMA
======================
Este script prueba que el firmador manual funciona con Object Id
"""

import os
import sys

# Configurar para usar firmador manual
os.environ['USE_MANUAL_XADES'] = 'true'
os.environ['USE_SRI_EC_IMPL'] = 'false'
os.environ['DJANGO_SETTINGS_MODULE'] = 'sistema.settings'

sys.path.insert(0, r'C:\Users\CORE I7\Desktop\catalinafact')

import django
django.setup()

from inventario.sri.firmador_xades import firmar_xml_xades_bes
from inventario.models import Opciones
from lxml import etree

print("="*80)
print("PRUEBA FIRMA XADES-BES CON OBJECT ID")
print("="*80)

# Crear XML de prueba
xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.0.0">
    <infoTributaria>
        <ambiente>1</ambiente>
        <tipoEmision>1</tipoEmision>
        <razonSocial>ALP SOLUCIONES SERVICIOS C A</razonSocial>
        <ruc>2390054060001</ruc>
        <claveAcceso>1710202501239005406000112019990000000190000000112</claveAcceso>
        <codDoc>01</codDoc>
        <estab>001</estab>
        <ptoEmi>999</ptoEmi>
        <secuencial>000000019</secuencial>
        <dirMatriz>VIA QUITO Y RIO YAMBOYA</dirMatriz>
    </infoTributaria>
    <infoFactura>
        <fechaEmision>17/10/2025</fechaEmision>
        <dirEstablecimiento>VIA QUITO Y RIO YAMBOYA</dirEstablecimiento>
        <obligadoContabilidad>SI</obligadoContabilidad>
        <tipoIdentificacionComprador>05</tipoIdentificacionComprador>
        <razonSocialComprador>CONSUMIDOR FINAL</razonSocialComprador>
        <identificacionComprador>9999999999999</identificacionComprador>
        <totalSinImpuestos>100.00</totalSinImpuestos>
        <totalDescuento>0.00</totalDescuento>
        <totalConImpuestos>
            <totalImpuesto>
                <codigo>2</codigo>
                <codigoPorcentaje>4</codigoPorcentaje>
                <baseImponible>100.00</baseImponible>
                <valor>15.00</valor>
            </totalImpuesto>
        </totalConImpuestos>
        <propina>0.00</propina>
        <importeTotal>115.00</importeTotal>
        <moneda>DOLAR</moneda>
        <pagos>
            <pago>
                <formaPago>01</formaPago>
                <total>115.00</total>
            </pago>
        </pagos>
    </infoFactura>
    <detalles>
        <detalle>
            <codigoPrincipal>SERV001</codigoPrincipal>
            <descripcion>SERVICIO DE PRUEBA</descripcion>
            <cantidad>1.000000</cantidad>
            <precioUnitario>100.000000</precioUnitario>
            <descuento>0.00</descuento>
            <precioTotalSinImpuesto>100.00</precioTotalSinImpuesto>
            <impuestos>
                <impuesto>
                    <codigo>2</codigo>
                    <codigoPorcentaje>4</codigoPorcentaje>
                    <tarifa>15.00</tarifa>
                    <baseImponible>100.00</baseImponible>
                    <valor>15.00</valor>
                </impuesto>
            </impuestos>
        </detalle>
    </detalles>
</factura>"""

# Guardar XML
xml_path = "factura_prueba_019.xml"
with open(xml_path, 'wb') as f:
    f.write(xml_content)

xml_firmado_path = "factura_prueba_019_firmada.xml"

print(f"\n[1] XML creado: {xml_path}")
print(f"[2] Obteniendo configuracion de firma...")

# Obtener opciones del tenant 1
try:
    opciones = Opciones.objects.get(id=1)
    print(f"[OK] Configuracion cargada - Certificado: {opciones.firma_electronica.name}")
except Exception as e:
    print(f"[ERROR] No se pudo cargar configuracion: {e}")
    print("[INFO] Verifica que exista un Opciones con id=1 y certificado configurado")
    sys.exit(1)

print(f"\n[3] Firmando XML con firmador manual (Object con Id)...")

# Firmar
try:
    resultado = firmar_xml_xades_bes(
        xml_path,
        xml_firmado_path,
        opciones=opciones
    )
    
    if resultado:
        print("[OK] FIRMA EXITOSA!")
        
        # Verificar estructura
        print("\n[4] Verificando estructura del XML firmado...")
        
        with open(xml_firmado_path, 'rb') as f:
            xml_firmado = f.read()
        
        tree = etree.fromstring(xml_firmado)
        ns = {
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
            'etsi': 'http://uri.etsi.org/01903/v1.3.2#'
        }
        
        sig = tree.find('.//ds:Signature', ns)
        if sig is not None:
            sig_id = sig.get('Id', 'N/A')
            print(f"  [OK] Signature Id: {sig_id}")
            
            # VERIFICAR OBJECT CON ID (CRITICO)
            obj = sig.find('ds:Object', ns)
            if obj is not None:
                obj_id = obj.get('Id')
                if obj_id:
                    print(f"  [OK] Object Id: {obj_id}")
                    print("  [OK] *** CRITICO PARA SRI - Object TIENE Id ***")
                else:
                    print("  [ERROR] Object NO tiene Id - FALTA CORRECCION")
            
            # KeyInfo
            key_info = sig.find('.//ds:KeyInfo', ns)
            if key_info is not None:
                ki_id = key_info.get('Id', 'N/A')
                print(f"  [OK] KeyInfo Id: {ki_id}")
                
                # KeyValue
                key_value = key_info.find('ds:KeyValue', ns)
                if key_value is not None:
                    print(f"  [OK] KeyValue presente (RSA)")
            
            # Referencias
            signed_info = sig.find('ds:SignedInfo', ns)
            if signed_info is not None:
                refs = signed_info.findall('ds:Reference', ns)
                print(f"  [OK] {len(refs)} referencias")
                
                for i, ref in enumerate(refs, 1):
                    uri = ref.get('URI', '')
                    ref_type = ref.get('Type', '')
                    transforms = ref.findall('.//ds:Transform', ns)
                    
                    if 'comprobante' in uri:
                        print(f"    Ref {i}: Comprobante ({len(transforms)} transforms)")
                    elif 'SignedProperties' in ref_type:
                        print(f"    Ref {i}: SignedProperties ({len(transforms)} transforms)")
                    else:
                        print(f"    Ref {i}: KeyInfo ({len(transforms)} transforms)")
        
        print("\n" + "="*80)
        print("VERIFICACION COMPLETADA")
        print("="*80)
        print(f"\nXML firmado guardado en: {xml_firmado_path}")
        print("\nPROXIMOS PASOS:")
        print("1. Revisa el archivo firmado")
        print("2. Firma una factura REAL desde la aplicacion web")
        print("3. Envia al SRI y verifica si Error 39 desaparece")
        print("\nSi Object tiene Id, la firma ahora coincide 100% con XMLs autorizados!")
        
    else:
        print("[ERROR] Firma fallida - Revisa los logs")
        
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
