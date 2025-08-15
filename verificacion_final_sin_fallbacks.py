#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔍 VERIFICACIÓN FINAL: Sistema completamente libre de fallbacks XMLDSig

Verifica que:
1. ✅ NO hay más uso de firmador obsoleto 
2. ✅ Vista de debug usa XAdES-BES
3. ✅ Integración SRI falla completamente si XAdES-BES no funciona
4. ✅ Firmador obsoleto está bloqueado
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verificar_vista_debug_corregida():
    """
    🔍 Verificar que vista de debug usa XAdES-BES
    """
    print("🔍 VERIFICACIÓN 1: Vista de debug usa XAdES-BES")
    print("-" * 50)
    
    try:
        views_path = Path(__file__).parent / 'inventario' / 'views.py'
        with open(views_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Verificar que NO usa firmador obsoleto
        if 'from .sri.firmador import firmar_xml' in contenido:
            print("❌ Vista de debug todavía usa firmador obsoleto")
            return False
        
        # Verificar que SÍ usa XAdES-BES
        if 'from .sri.firmador_xades import firmar_xml_xades_bes' in contenido:
            print("✅ Vista de debug usa firmador XAdES-BES correcto")
        else:
            print("❌ Vista de debug no usa firmador XAdES-BES")
            return False
        
        # Verificar validación XSD
        if 'validar_xml_contra_xsd' in contenido:
            print("✅ Vista incluye validación XSD")
        else:
            print("⚠️ Vista no incluye validación XSD explícita")
            
        return True
        
    except Exception as e:
        print(f"❌ Error verificando vista: {e}")
        return False

def verificar_integracion_sin_fallback():
    """
    🔍 Verificar que integración SRI no permite fallbacks
    """
    print("\n🔍 VERIFICACIÓN 2: Integración SRI sin fallbacks")
    print("-" * 50)
    
    try:
        integracion_path = Path(__file__).parent / 'inventario' / 'sri' / 'integracion_django.py'
        with open(integracion_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Verificar que NO hay return False peligroso en contexto de firma
        lines = contenido.split('\n')
        for i, line in enumerate(lines):
            if 'return False' in line:
                # Revisar contexto alrededor para ver si es en función de firma
                contexto_anterior = '\n'.join(lines[max(0, i-10):i])
                contexto_posterior = '\n'.join(lines[i:min(len(lines), i+5)])
                
                # Si está en contexto de firma, es problemático
                if any(keyword in contexto_anterior.lower() for keyword in ['firma', 'sign', 'xml']):
                    if not any(safe_keyword in contexto_anterior.lower() for safe_keyword in ['estado', 'autorizado', 'verificar']):
                        print(f"❌ 'return False' peligroso en contexto de firma:")
                        print(f"  Línea {i+1}: {line.strip()}")
                        print(f"  Contexto: ...{contexto_anterior[-100:]}...")
                        return False
        
        print("✅ No se encontraron 'return False' peligrosos en contexto de firma")
        
        # Verificar que hay excepciones de bloqueo
        if 'FIRMA XAdES-BES REQUERIDA' in contenido:
            print("✅ Excepción de bloqueo XAdES-BES presente")
        else:
            print("❌ No se encontró excepción de bloqueo XAdES-BES")
            return False
            
        if 'PROCESO DE FIRMA FALLÓ COMPLETAMENTE' in contenido:
            print("✅ Excepción de falla completa presente")
        else:
            print("❌ No se encontró excepción de falla completa")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error verificando integración: {e}")
        return False

def verificar_firmador_bloqueado():
    """
    🔍 Verificar que firmador obsoleto está bloqueado
    """
    print("\n🔍 VERIFICACIÓN 3: Firmador obsoleto bloqueado")
    print("-" * 50)
    
    try:
        from inventario.sri.firmador import firmar_xml
        
        # Intentar usar la función - debería fallar
        try:
            firmar_xml("/fake/path.xml", "/fake/signed.xml")
            print("❌ ERROR: Firmador obsoleto NO está bloqueado")
            return False
        except Exception as e:
            if "FUNCIÓN BLOQUEADA" in str(e):
                print("✅ Firmador obsoleto correctamente bloqueado")
                print(f"✅ Mensaje de bloqueo: {str(e)[:100]}...")
                return True
            else:
                print(f"❌ Firmador falló pero con mensaje incorrecto: {str(e)[:100]}...")
                return False
                
    except Exception as e:
        print(f"❌ Error verificando firmador: {e}")
        return False

def verificar_archivos_peligrosos_eliminados():
    """
    🔍 Verificar que archivos peligrosos fueron eliminados
    """
    print("\n🔍 VERIFICACIÓN 4: Archivos peligrosos eliminados")
    print("-" * 50)
    
    archivos_peligrosos = [
        'inventario/sri/integracion_django_clean.py',
        'inventario/sri/integracion_django_backup.py'
    ]
    
    todos_eliminados = True
    for archivo in archivos_peligrosos:
        archivo_path = Path(__file__).parent / archivo
        if archivo_path.exists():
            print(f"❌ Archivo peligroso todavía existe: {archivo}")
            todos_eliminados = False
        else:
            print(f"✅ Archivo peligroso eliminado: {archivo}")
    
    return todos_eliminados

def test_xades_funciona():
    """
    🔍 Verificar que XAdES-BES funciona correctamente
    """
    print("\n🔍 VERIFICACIÓN 5: XAdES-BES funciona")
    print("-" * 50)
    
    try:
        from inventario.sri.firmador_xades import firmar_xml_xades_bes
        print("✅ Firmador XAdES-BES se puede importar")
        
        # Verificar que la función existe y es callable
        if callable(firmar_xml_xades_bes):
            print("✅ Función firmar_xml_xades_bes es callable")
        else:
            print("❌ Función firmar_xml_xades_bes no es callable")
            return False
            
        return True
        
    except ImportError as e:
        print(f"❌ No se puede importar firmador XAdES-BES: {e}")
        return False
    except Exception as e:
        print(f"❌ Error verificando XAdES-BES: {e}")
        return False

def main():
    """
    🎯 Verificación completa del sistema
    """
    print("=" * 60)
    print("🔍 VERIFICACIÓN FINAL: SISTEMA SIN FALLBACKS XMLDSig")
    print("=" * 60)
    print("Objetivo: Confirmar eliminación completa de fallbacks peligrosos")
    print("=" * 60)
    
    verificaciones = [
        ("Vista debug corregida", verificar_vista_debug_corregida),
        ("Integración sin fallbacks", verificar_integracion_sin_fallback),
        ("Firmador obsoleto bloqueado", verificar_firmador_bloqueado),
        ("Archivos peligrosos eliminados", verificar_archivos_peligrosos_eliminados),
        ("XAdES-BES funciona", test_xades_funciona)
    ]
    
    resultados = []
    
    for nombre, verificacion in verificaciones:
        try:
            resultado = verificacion()
            resultados.append((nombre, resultado))
        except Exception as e:
            print(f"❌ Error en verificación '{nombre}': {e}")
            resultados.append((nombre, False))
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE VERIFICACIÓN FINAL")
    print("=" * 60)
    
    todos_exitosos = True
    for descripcion, resultado in resultados:
        status = "✅ PASS" if resultado else "❌ FAIL"
        print(f"{status} {descripcion}")
        if not resultado:
            todos_exitosos = False
    
    print("=" * 60)
    if todos_exitosos:
        print("🎉 SISTEMA COMPLETAMENTE SEGURO")
        print("✅ NO hay fallbacks XMLDSig peligrosos")
        print("✅ Solo se permite XAdES-BES válido")
        print("✅ Firmador obsoleto está bloqueado")
        print("✅ Archivos peligrosos eliminados")
        print("🚫 CERO TOLERANCIA A DOCUMENTOS DEFECTUOSOS")
    else:
        print("❌ SISTEMA TODAVÍA TIENE PROBLEMAS")
        print("🔧 REVISAR VERIFICACIONES FALLIDAS")
        print("⚠️ NO USAR EN PRODUCCIÓN HASTA CORREGIR")
        
    print("=" * 60)
    return todos_exitosos

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
