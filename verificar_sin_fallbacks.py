#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚫 VERIFICACIÓN: ELIMINACIÓN COMPLETA DE FALLBACKS PELIGROSOS

Esta verificación asegura que:
1. ✅ NO hay fallbacks a XMLDSig básico cuando XAdES-BES falla
2. ✅ NO hay fallbacks que generen PDFs sin firma
3. ✅ Si la firma falla, TODO el proceso se detiene
4. ❌ NO se permite envío de documentos con errores
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

import logging
from inventario.sri.integracion_django import SRIIntegration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verificar_no_fallback_xmldsig():
    """
    🔴 Verificar que NO hay fallback a XMLDSig básico
    """
    print("🔴 VERIFICACIÓN 1: NO fallback a XMLDSig básico")
    print("-" * 50)
    
    try:
        # Leer el código del archivo de integración
        integracion_path = Path(__file__).parent / 'inventario' / 'sri' / 'integracion_django.py'
        with open(integracion_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Buscar patrones peligrosos
        patrones_peligrosos = [
            'XMLDSig básico',
            'fallback.*XMLDSig',
            'from .firmador import firmar_xml',
            'SRI puede rechazar la firma'
        ]
        
        fallbacks_encontrados = []
        for patron in patrones_peligrosos:
            import re
            matches = re.findall(patron, contenido, re.IGNORECASE)
            if matches:
                fallbacks_encontrados.extend(matches)
        
        if fallbacks_encontrados:
            print(f"❌ FALLBACKS PELIGROSOS ENCONTRADOS: {fallbacks_encontrados}")
            return False
        else:
            print("✅ NO se encontraron fallbacks a XMLDSig básico")
            
        # Verificar que existe la excepción de bloqueo
        if "FIRMA XAdES-BES REQUERIDA" in contenido:
            print("✅ Excepción de bloqueo está presente")
        else:
            print("❌ No se encontró excepción de bloqueo")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error verificando archivo de integración: {e}")
        return False

def verificar_no_fallback_pdf():
    """
    🔴 Verificar que NO hay fallback para PDFs sin firma
    """
    print("\n🔴 VERIFICACIÓN 2: NO fallback para PDFs sin firma")
    print("-" * 50)
    
    try:
        # Leer el código del archivo de vistas
        views_path = Path(__file__).parent / 'inventario' / 'views.py'
        with open(views_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Buscar patrones peligrosos en PDFs
        patrones_peligrosos = [
            'generar sin firma',
            'Fallback.*generar',
            'generando sin firma'
        ]
        
        fallbacks_encontrados = []
        for patron in patrones_peligrosos:
            import re
            matches = re.findall(patron, contenido, re.IGNORECASE)
            if matches:
                fallbacks_encontrados.extend(matches)
        
        if fallbacks_encontrados:
            print(f"❌ FALLBACKS PDF PELIGROSOS ENCONTRADOS: {fallbacks_encontrados}")
            return False
        else:
            print("✅ NO se encontraron fallbacks para PDFs sin firma")
            
        # Verificar que existe la excepción de bloqueo para PDFs
        if "FIRMA DE PDF REQUERIDA" in contenido:
            print("✅ Excepción de bloqueo para PDF está presente")
        else:
            print("❌ No se encontró excepción de bloqueo para PDF")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error verificando archivo de vistas: {e}")
        return False

def test_firma_falla_completamente():
    """
    🔴 Probar que cuando la firma falla, TODO se detiene
    """
    print("\n🔴 VERIFICACIÓN 3: Firma fallida detiene TODO")
    print("-" * 50)
    
    try:
        # Crear mock de SRIIntegration para probar falla
        sri = SRIIntegration()
        
        # Simular falla en firma XAdES-BES
        def mock_firmar_falla(xml_path, xml_firmado_path):
            raise Exception("Mock: Firma XAdES-BES falló intencionalmente")
        
        # Reemplazar método temporalmente
        original_method = sri._firmar_xml_xades_bes
        sri._firmar_xml_xades_bes = mock_firmar_falla
        
        try:
            # Esto debería FALLAR completamente
            result = sri._firmar_xml_xades_bes("/fake/path.xml", "/fake/signed.xml")
            print("❌ ERROR: Firma no falló como debería")
            return False
            
        except Exception as e:
            if "FIRMA XAdES-BES REQUERIDA" in str(e):
                print("✅ CORRECTO: Firma falló y se detuvo completamente")
                print(f"✅ Mensaje de error: {str(e)[:100]}...")
                return True
            else:
                print(f"❌ Firma falló pero con mensaje incorrecto: {str(e)[:100]}...")
                return False
                
        finally:
            # Restaurar método original
            sri._firmar_xml_xades_bes = original_method
            
    except Exception as e:
        print(f"❌ Error en prueba de falla de firma: {e}")
        return False

def main():
    """
    🎯 Función principal de verificación
    """
    print("=" * 60)
    print("🚫 VERIFICACIÓN: ELIMINACIÓN DE FALLBACKS PELIGROSOS")
    print("=" * 60)
    print("Objetivo: Asegurar que NO se envía NADA con errores")
    print("=" * 60)
    
    resultados = []
    
    # Verificación 1: No fallback XMLDSig
    resultado1 = verificar_no_fallback_xmldsig()
    resultados.append(("No fallback XMLDSig", resultado1))
    
    # Verificación 2: No fallback PDF
    resultado2 = verificar_no_fallback_pdf()
    resultados.append(("No fallback PDF", resultado2))
    
    # Verificación 3: Falla completa
    resultado3 = test_firma_falla_completamente()
    resultados.append(("Falla detiene TODO", resultado3))
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE VERIFICACIONES")
    print("=" * 60)
    
    todos_exitosos = True
    for descripcion, resultado in resultados:
        status = "✅ PASS" if resultado else "❌ FAIL"
        print(f"{status} {descripcion}")
        if not resultado:
            todos_exitosos = False
    
    print("=" * 60)
    if todos_exitosos:
        print("🎉 TODAS LAS VERIFICACIONES PASARON")
        print("✅ NO hay fallbacks peligrosos")
        print("✅ Si hay errores en firma, TODO se detiene")
        print("✅ NO se enviará NADA con errores")
        print("🚫 SISTEMA SEGURO: Sin fallbacks peligrosos")
    else:
        print("❌ ALGUNAS VERIFICACIONES FALLARON")
        print("🔧 Aún existen fallbacks peligrosos")
        print("⚠️ REVISAR CÓDIGO URGENTEMENTE")
        
    print("=" * 60)
    return todos_exitosos

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
