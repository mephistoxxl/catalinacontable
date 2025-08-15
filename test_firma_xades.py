#!/usr/bin/env python
"""
Script de prueba para verificar la implementación de firma XAdES-BES
Verifica que los XMLs se firmen correctamente con XAdES-BES en lugar de XMLDSig básico
"""
import os
import sys
import django
from lxml import etree

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura, Opciones

def verificar_configuracion_firma():
    """Verificar que la configuración de firma esté disponible"""
    print("🔍 VERIFICACIÓN DE CONFIGURACIÓN DE FIRMA")
    print("=" * 50)
    
    opciones = Opciones.objects.first()
    if not opciones:
        print("❌ No hay configuración de Opciones")
        return False
    
    if not opciones.firma_electronica:
        print("❌ No hay archivo de firma electrónica configurado")
        return False
    
    if not opciones.password_firma:
        print("❌ No hay contraseña de firma configurada")
        return False
    
    # Verificar que el archivo existe
    if not os.path.exists(opciones.firma_electronica.path):
        print(f"❌ Archivo de firma no encontrado: {opciones.firma_electronica.path}")
        return False
    
    print("✅ Configuración de firma disponible:")
    print(f"   Archivo: {opciones.firma_electronica.path}")
    print(f"   Tamaño: {os.path.getsize(opciones.firma_electronica.path)} bytes")
    
    return True

def test_firma_xades_bes():
    """Test de firma XAdES-BES"""
    print("\n🎯 TEST DE FIRMA XAdES-BES")
    print("=" * 50)
    
    if not verificar_configuracion_firma():
        return False
    
    # Buscar una factura para test
    factura = Factura.objects.first()
    if not factura:
        print("❌ No hay facturas disponibles para test")
        return False
    
    print(f"📄 Usando factura ID {factura.id} para test")
    
    try:
        # Test 1: Crear XML temporal para test
        from inventario.sri.integracion_django import SRIIntegration
        integration = SRIIntegration()
        
        # Generar XML de test
        xml_path = f"/tmp/test_factura_{factura.id}.xml"
        xml_content = integration.generar_xml_factura(factura, validar_xsd=False)
        
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        print(f"✅ XML generado: {xml_path}")
        
        # Test 2: Probar firma XAdES-BES
        xml_firmado_path = xml_path.replace('.xml', '_firmado_xades.xml')
        
        try:
            from inventario.sri.firmador_xades import firmar_xml_xades_bes
            success = firmar_xml_xades_bes(xml_path, xml_firmado_path)
            
            if success and os.path.exists(xml_firmado_path):
                print("✅ Firma XAdES-BES exitosa!")
                analizar_xml_firmado(xml_firmado_path)
            else:
                print("❌ Firma XAdES-BES falló")
                
        except Exception as e:
            print(f"❌ Error en firma XAdES-BES: {e}")
            
            # Fallback: Probar firma básica
            print("\n🔄 Probando firma XMLDSig básica como fallback...")
            try:
                from inventario.sri.firmador import firmar_xml
                xml_basico_path = xml_path.replace('.xml', '_firmado_basico.xml')
                firmar_xml(xml_path, xml_basico_path)
                
                if os.path.exists(xml_basico_path):
                    print("✅ Firma XMLDSig básica exitosa")
                    analizar_xml_firmado(xml_basico_path, es_xades=False)
                else:
                    print("❌ Firma XMLDSig básica también falló")
            except Exception as e2:
                print(f"❌ Error en firma básica: {e2}")
        
        # Limpiar archivos temporales
        for path in [xml_path, xml_firmado_path, xml_path.replace('.xml', '_firmado_basico.xml')]:
            if os.path.exists(path):
                os.remove(path)
                
    except Exception as e:
        print(f"❌ Error general en test: {e}")
        return False
    
    return True

def analizar_xml_firmado(xml_path, es_xades=True):
    """Analizar XML firmado para verificar elementos XAdES"""
    print(f"\n🔍 ANÁLISIS DE XML FIRMADO: {os.path.basename(xml_path)}")
    print("-" * 40)
    
    try:
        with open(xml_path, 'rb') as f:
            xml_content = f.read()
        
        tree = etree.fromstring(xml_content)
        
        # Definir namespaces
        namespaces = {
            'ds': 'http://www.w3.org/2000/09/xmldsig#',
            'xades': 'http://uri.etsi.org/01903/v1.3.2#'
        }
        
        # Verificar elementos básicos de firma
        signature = tree.find('.//ds:Signature', namespaces)
        if signature is not None:
            print("✅ Elemento Signature encontrado")
        else:
            print("❌ No se encontró elemento Signature")
            return
        
        # Verificar SignedInfo
        signed_info = signature.find('.//ds:SignedInfo', namespaces)
        if signed_info is not None:
            print("✅ SignedInfo encontrado")
        else:
            print("❌ SignedInfo no encontrado")
        
        # Verificar SignatureValue
        signature_value = signature.find('.//ds:SignatureValue', namespaces)
        if signature_value is not None and signature_value.text and len(signature_value.text.strip()) > 0:
            print("✅ SignatureValue encontrado")
        else:
            print("❌ SignatureValue vacío o no encontrado")
        
        # Verificar KeyInfo
        key_info = signature.find('.//ds:KeyInfo', namespaces)
        if key_info is not None:
            print("✅ KeyInfo encontrado")
        else:
            print("❌ KeyInfo no encontrado")
        
        if es_xades:
            # Verificar elementos XAdES específicos
            print("\n🔍 Verificando elementos XAdES-BES:")
            
            qualifying_props = signature.find('.//xades:QualifyingProperties', namespaces)
            if qualifying_props is not None:
                print("✅ QualifyingProperties encontrado")
            else:
                print("❌ QualifyingProperties no encontrado")
                return
            
            signed_props = signature.find('.//xades:SignedProperties', namespaces)
            if signed_props is not None:
                print("✅ SignedProperties encontrado")
            else:
                print("❌ SignedProperties no encontrado")
            
            signing_time = signature.find('.//xades:SigningTime', namespaces)
            if signing_time is not None:
                print(f"✅ SigningTime: {signing_time.text}")
            else:
                print("❌ SigningTime no encontrado")
            
            signing_cert = signature.find('.//xades:SigningCertificate', namespaces)
            if signing_cert is not None:
                print("✅ SigningCertificate encontrado")
            else:
                print("❌ SigningCertificate no encontrado")
        
        print(f"\n📊 Tamaño del XML firmado: {len(xml_content)} bytes")
        
    except Exception as e:
        print(f"❌ Error al analizar XML: {e}")

def test_comparacion_firmas():
    """Comparar XMLDSig básico vs XAdES-BES"""
    print("\n📊 COMPARACIÓN DE MÉTODOS DE FIRMA")
    print("=" * 50)
    
    print("XMLDSig básico:")
    print("  ✅ Más simple de implementar")
    print("  ❌ SRI puede rechazarlo (no cumple especificación)")
    print("  ❌ Solo elementos ds:Signature básicos")
    
    print("\nXAdES-BES:")
    print("  ✅ Cumple especificación SRI")
    print("  ✅ Incluye timestamp y certificado")
    print("  ✅ Mayor probabilidad de aceptación")
    print("  ⚠️  Más complejo de implementar")

if __name__ == "__main__":
    print("🔐 VERIFICADOR DE FIRMA XAdES-BES PARA SRI")
    print("=" * 60)
    
    test_firma_xades_bes()
    test_comparacion_firmas()
    
    print("\n✅ VERIFICACIÓN COMPLETADA")
    print("\n💡 RECOMENDACIÓN:")
    print("   - Si XAdES-BES funciona: ¡Úsalo para producción!")
    print("   - Si falla: Revisar certificado y librerías")
    print("   - XMLDSig básico solo como último recurso")
