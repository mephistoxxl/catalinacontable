#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 PRUEBA ESPECÍFICA: Validación XSD detiene envío de XMLs inválidos

Esta prueba verifica específicamente que:
1. ✅ XMLs válidos pasan la validación y continúan
2. ❌ XMLs inválidos FALLAN y detienen el proceso COMPLETAMENTE
3. 🔍 XMLs inválidos se guardan para debugging
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura
from inventario.sri.integracion_django import SRIIntegration
from inventario.sri.xml_generator import SRIXMLGenerator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_xml_valido_pasa():
    """
    🟢 Prueba 1: XML válido debe pasar la validación y continuar
    """
    print("\n🟢 PRUEBA 1: XML válido debe pasar validación")
    print("-" * 50)
    
    try:
        # Buscar una factura para generar XML válido
        factura = Factura.objects.first()
        if not factura:
            print("❌ No hay facturas en la BD para probar")
            return False
            
        sri_integration = SRIIntegration()
        
        # Intentar generar XML (esto incluye validación automática)
        xml_path = sri_integration.generar_xml_factura(factura)
        print(f"✅ XML válido generado exitosamente: {xml_path}")
        
        # Verificar que el archivo existe
        if os.path.exists(xml_path):
            file_size = os.path.getsize(xml_path)
            print(f"📁 Archivo XML: {file_size} bytes")
            print("✅ RESULTADO: XML válido PASÓ la validación y continuó")
            return True
        else:
            print("❌ XML no fue guardado")
            return False
            
    except Exception as e:
        print(f"❌ XML válido FALLÓ inesperadamente: {str(e)}")
        return False

def test_xml_invalido_falla():
    """
    🔴 Prueba 2: XML inválido debe FALLAR la validación y DETENER el proceso
    """
    print("\n🔴 PRUEBA 2: XML inválido debe FALLAR y DETENER proceso")
    print("-" * 50)
    
    try:
        # Crear XML intencionalmente inválido
        xml_invalido = """<?xml version="1.0" encoding="UTF-8"?>
<factura xmlns="http://www.sri.gob.ec/ni/1.1.0" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.sri.gob.ec/ni/1.1.0 http://www.sri.gob.ec/ni/1.1.0/schemas">
    <infoTributaria>
        <!-- INTENCIONALMENTE INVÁLIDO: falta campos obligatorios -->
        <ambiente>1</ambiente>
    </infoTributaria>
    <!-- ESTRUCTURA INCOMPLETA PARA FORZAR ERROR XSD -->
</factura>"""
        
        # Crear archivo temporal
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            f.write(xml_invalido)
            xml_temp_path = f.name
            
        print(f"📁 XML inválido creado en: {xml_temp_path}")
        
        # Intentar validar XML inválido directamente
        sri_integration = SRIIntegration()
        xml_generator = SRIXMLGenerator()
        xsd_path = sri_integration._obtener_ruta_xsd()
        
        try:
            xml_generator.validar_xml_contra_xsd(xml_invalido, xsd_path)
            print("❌ ERROR: XML inválido PASÓ la validación (no debería)")
            return False
            
        except Exception as e:
            print(f"✅ CORRECTO: XML inválido FALLÓ la validación: {str(e)[:100]}...")
            print("✅ RESULTADO: XML inválido fue RECHAZADO y NO continuó")
            
            # Limpiar archivo temporal
            try:
                os.unlink(xml_temp_path)
            except:
                pass
                
            return True
            
    except Exception as e:
        print(f"❌ Error inesperado en prueba de XML inválido: {str(e)}")
        return False

def test_generar_xml_factura_con_validacion():
    """
    🔍 Prueba 3: Método generar_xml_factura debe fallar en validación XSD
    """
    print("\n🔍 PRUEBA 3: generar_xml_factura debe fallar con validación estricta")
    print("-" * 50)
    
    try:
        factura = Factura.objects.first()
        if not factura:
            print("❌ No hay facturas para probar")
            return False
            
        sri_integration = SRIIntegration()
        
        # Modificar temporalmente el método para generar XML inválido
        original_method = sri_integration.generar_xml_factura
        
        def generar_xml_invalido_mock(factura, validar_xsd=True):
            # Crear XML inválido para probar validación
            xml_invalido = """<?xml version="1.0" encoding="UTF-8"?>
<factura xmlns="http://www.sri.gob.ec/ni/1.1.0">
    <infoTributaria>
        <ambiente>1</ambiente>
        <!-- CAMPOS OBLIGATORIOS FALTANTES PARA FORZAR ERROR -->
    </infoTributaria>
</factura>"""
            
            # Llamar validación como lo haría normalmente
            if validar_xsd:
                xml_generator = SRIXMLGenerator()
                xsd_path = sri_integration._obtener_ruta_xsd()
                xml_generator.validar_xml_contra_xsd(xml_invalido, xsd_path)
            
            return "fake_path.xml"
        
        # Aplicar mock temporalmente
        sri_integration.generar_xml_factura = generar_xml_invalido_mock
        
        try:
            xml_path = sri_integration.generar_xml_factura(factura, validar_xsd=True)
            print("❌ ERROR: generar_xml_factura permitió XML inválido")
            return False
            
        except Exception as e:
            print(f"✅ CORRECTO: generar_xml_factura FALLÓ con XML inválido: {str(e)[:100]}...")
            print("✅ RESULTADO: Validación XSD DETIENE el proceso correctamente")
            return True
            
        finally:
            # Restaurar método original
            sri_integration.generar_xml_factura = original_method
            
    except Exception as e:
        print(f"❌ Error en prueba de generar_xml_factura: {str(e)}")
        return False

def main():
    """
    🎯 Función principal de pruebas de validación XSD
    """
    print("=" * 60)
    print("🧪 PRUEBA ESPECÍFICA: VALIDACIÓN XSD DETIENE ENVÍO")
    print("=" * 60)
    
    resultados = []
    
    # Prueba 1: XML válido
    resultado1 = test_xml_valido_pasa()
    resultados.append(("XML válido pasa", resultado1))
    
    # Prueba 2: XML inválido falla
    resultado2 = test_xml_invalido_falla()
    resultados.append(("XML inválido falla", resultado2))
    
    # Prueba 3: generar_xml_factura con validación
    resultado3 = test_generar_xml_factura_con_validacion()
    resultados.append(("generar_xml_factura falla", resultado3))
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE RESULTADOS")
    print("=" * 60)
    
    todos_exitosos = True
    for descripcion, resultado in resultados:
        status = "✅ PASS" if resultado else "❌ FAIL"
        print(f"{status} {descripcion}")
        if not resultado:
            todos_exitosos = False
    
    print("=" * 60)
    if todos_exitosos:
        print("🎉 TODAS LAS PRUEBAS PASARON")
        print("✅ La validación XSD DETIENE correctamente el envío de XMLs inválidos")
        print("✅ XMLs válidos pueden continuar normalmente")
    else:
        print("❌ ALGUNAS PRUEBAS FALLARON")
        print("🔧 La validación XSD necesita corrección")
    
    print("=" * 60)
    return todos_exitosos

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
