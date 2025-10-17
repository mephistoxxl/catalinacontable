#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba para firmar XML con la nueva implementación
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, r'C:\Users\CORE I7\Desktop\catalinafact')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.sri.firmador_xades_manual import firmar_xml_xades_bes_manual

print("="*80)
print("PRUEBA DE FIRMA CON ESTRUCTURA AUTORIZADA DEL SRI")
print("="*80)

# Ruta del XML sin firmar (usando la empresa que tiene configuración)
xml_sin_firmar = r"C:\Users\CORE I7\Desktop\catalinafact\media\facturas\1713959011001\xml\factura_001-999-000000049_20251017_143718.xml"

# Verificar si existe
import os
if not os.path.exists(xml_sin_firmar):
    # Crear XML de prueba simple
    xml_content = '''<?xml version="1.0" encoding="utf-8"?>
<factura id="comprobante" version="1.1.0">
  <infoTributaria>
    <ambiente>1</ambiente>
    <tipoEmision>1</tipoEmision>
    <razonSocial>PUMALPA MORILLO LINA YOLANDA</razonSocial>
    <nombreComercial>MARIA SOLEDAD BOUTIQUE</nombreComercial>
    <ruc>1713959011001</ruc>
    <claveAcceso>1610202501171395901100110019990000000494942407312</claveAcceso>
    <codDoc>01</codDoc>
    <estab>001</estab>
    <ptoEmi>999</ptoEmi>
    <secuencial>000000049</secuencial>
    <dirMatriz>SANTO DOMINGO</dirMatriz>
  </infoTributaria>
  <infoFactura>
    <fechaEmision>16/10/2025</fechaEmision>
    <dirEstablecimiento>SANTO DOMINGO</dirEstablecimiento>
    <obligadoContabilidad>NO</obligadoContabilidad>
    <tipoIdentificacionComprador>05</tipoIdentificacionComprador>
    <razonSocialComprador>CONSUMIDOR FINAL</razonSocialComprador>
    <identificacionComprador>9999999999</identificacionComprador>
    <totalSinImpuestos>1.00</totalSinImpuestos>
    <totalDescuento>0.00</totalDescuento>
    <totalConImpuestos>
      <totalImpuesto>
        <codigo>2</codigo>
        <codigoPorcentaje>0</codigoPorcentaje>
        <baseImponible>1.00</baseImponible>
        <valor>0.00</valor>
      </totalImpuesto>
    </totalConImpuestos>
    <propina>0.00</propina>
    <importeTotal>1.00</importeTotal>
    <moneda>DOLAR</moneda>
  </infoFactura>
  <detalles>
    <detalle>
      <codigoPrincipal>PROD001</codigoPrincipal>
      <descripcion>PRODUCTO DE PRUEBA</descripcion>
      <cantidad>1.00</cantidad>
      <precioUnitario>1.00</precioUnitario>
      <descuento>0.00</descuento>
      <precioTotalSinImpuesto>1.00</precioTotalSinImpuesto>
    </detalle>
  </detalles>
</factura>'''
    os.makedirs(os.path.dirname(xml_sin_firmar), exist_ok=True)
    with open(xml_sin_firmar, 'w', encoding='utf-8') as f:
        f.write(xml_content)

# Firmar
print(f"\n📄 Firmando: {xml_sin_firmar}")
print("⏳ Procesando...\n")

try:
    # Determinar ruta del firmado
    import os
    from django.core.files import File
    xml_firmado_path = xml_sin_firmar.replace('.xml', '_firmado_test.xml')
    
    from inventario.models import Empresa, Opciones
    empresa = Empresa.objects.get(ruc="1713959011001")
    
    # Crear opciones temporales si no existen
    opciones, created = Opciones.objects.get_or_create(
        empresa=empresa,
        defaults={
            'password_firma': '1713959011'  # Password típico
        }
    )
    
    # Asignar archivo de firma si no tiene
    if not opciones.firma_electronica:
        p12_path = r"C:\Users\CORE I7\Desktop\catalinafact\firmas_secure\firmas\1713959011.p12"
        with open(p12_path, 'rb') as f:
            opciones.firma_electronica.save('firma.p12', File(f), save=True)
    
    resultado = firmar_xml_xades_bes_manual(
        xml_path=xml_sin_firmar,
        xml_firmado_path=xml_firmado_path,
        empresa=empresa
    )
    
    print(f"\n✅ ¡Firma completada exitosamente!")
    print(f"📁 Archivo firmado: {xml_firmado_path}")
    
    # Verificar estructura
    from lxml import etree
    with open(xml_firmado_path, 'rb') as f:
        tree = etree.parse(f)
        root = tree.getroot()
    
    ns = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
    
    # Contar referencias
    refs = root.findall('.//ds:Reference', ns)
    print(f"\n📊 Referencias en SignedInfo: {len(refs)}")
    for i, ref in enumerate(refs, 1):
        uri = ref.get('URI', '')
        ref_type = ref.get('Type', 'N/A')
        transforms = ref.findall('.//ds:Transform', ns)
        print(f"   {i}. URI={uri}, Type={ref_type}, Transforms={len(transforms)}")
        for t in transforms:
            print(f"      - {t.get('Algorithm')}")
    
    # Verificar CanonicalizationMethod
    c14n_method = root.find('.//ds:CanonicalizationMethod', ns)
    if c14n_method is not None:
        print(f"\n🔧 CanonicalizationMethod: {c14n_method.get('Algorithm')}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
