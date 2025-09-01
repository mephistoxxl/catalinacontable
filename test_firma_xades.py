#!/usr/bin/env python
"""
Script de prueba para verificar la implementación de firma XAdES-BES
Verifica que los XMLs se firmen correctamente con XAdES-BES en lugar de XMLDSig básico
"""
import os
import sys
import django
    try:
        # Test 1: Crear XML temporal para test
        from inventario.sri.integracion_django import SRIIntegration
        integration = SRIIntegration()

        if not factura.formas_pago.exists():
            caja = Caja.objects.filter(activo=True).first()
            if not caja:
                print("❌ No hay cajas activas")
                return False
            FormaPago.objects.create(
                factura=factura,
                forma_pago='01',
                caja=caja,
                total=factura.monto_general or Decimal('0.00')
            )

        # Generar XML de test (integration devuelve la RUTA del XML)
        xml_path = integration.generar_xml_factura(factura, validar_xsd=False)
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
        for path in [xml_firmado_path, xml_path.replace('.xml', '_firmado_basico.xml')]:
            if os.path.exists(path):
                os.remove(path)
                
    except Exception as e:
        print(f"❌ Error general en test: {e}")
        return False

        if not factura.formas_pago.exists():
            caja = Caja.objects.filter(activo=True).first()
            if not caja:
                print("❌ No hay cajas activas")
                return False
            FormaPago.objects.create(
                factura=factura,
                forma_pago='01',
                caja=caja,
                total=factura.monto_general or Decimal('0.00')
            )

    # Generar XML de test (integration devuelve la RUTA del XML)
    xml_path = integration.generar_xml_factura(factura, validar_xsd=False)
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
    for path in [xml_firmado_path, xml_path.replace('.xml', '_firmado_basico.xml')]:
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
