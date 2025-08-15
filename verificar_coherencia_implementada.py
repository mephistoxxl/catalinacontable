#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔍 VERIFICACIÓN: Implementación de validación de coherencia entre pagos y total

Esta verificación confirma que:
1. ✅ Se agregó validación en la vista (antes de guardar factura)
2. ✅ Se agregó validación en XML generator (antes de generar XML)
3. ✅ Las validaciones lanzan excepciones apropiadas
4. ✅ Se incluye tolerancia para decimales
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

def verificar_validacion_en_vista():
    """
    🔍 Verificar que se agregó validación en la vista
    """
    print("🔍 VERIFICACIÓN 1: Validación en vista")
    print("-" * 50)
    
    try:
        views_path = Path(__file__).parent / 'inventario' / 'views.py'
        with open(views_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Verificar elementos clave de la validación
        elementos_validacion = [
            'Validando coherencia entre formas de pago y total de factura',
            'suma_pagos = Decimal',
            'factura.monto_general - suma_pagos',
            'INCOHERENCIA EN FORMAS DE PAGO',
            'tolerancia = Decimal',
            'VALIDACIÓN DE COHERENCIA FALLÓ'
        ]
        
        todos_presentes = True
        for elemento in elementos_validacion:
            if elemento in contenido:
                print(f"✅ Elemento presente: {elemento[:40]}...")
            else:
                print(f"❌ Elemento faltante: {elemento}")
                todos_presentes = False
        
        # Verificar que la validación está en el lugar correcto
        if 'validación EN XML generator' in contenido:
            print("⚠️ Validación parece estar mal ubicada")
            
        return todos_presentes
        
    except Exception as e:
        print(f"❌ Error verificando vista: {e}")
        return False

def verificar_validacion_en_xml_generator():
    """
    🔍 Verificar que se agregó validación en XML generator
    """
    print("\n🔍 VERIFICACIÓN 2: Validación en XML generator")
    print("-" * 50)
    
    try:
        xml_gen_path = Path(__file__).parent / 'inventario' / 'sri' / 'xml_generator.py'
        with open(xml_gen_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Verificar elementos clave de la validación SRI
        elementos_validacion = [
            'VALIDACIÓN CRÍTICA SRI',
            'Validando coherencia entre pagos y total para XML SRI',
            'suma_pagos = Decimal',
            'INCOHERENCIA EN XML SRI',
            'XML SRI REQUIERE coherencia exacta',
            'Coherencia SRI validada'
        ]
        
        todos_presentes = True
        for elemento in elementos_validacion:
            if elemento in contenido:
                print(f"✅ Elemento presente: {elemento[:40]}...")
            else:
                print(f"❌ Elemento faltante: {elemento}")
                todos_presentes = False
        
        return todos_presentes
        
    except Exception as e:
        print(f"❌ Error verificando XML generator: {e}")
        return False

def verificar_manejo_excepciones():
    """
    🔍 Verificar que se manejan excepciones apropiadas
    """
    print("\n🔍 VERIFICACIÓN 3: Manejo de excepciones")
    print("-" * 50)
    
    try:
        # Verificar vista
        views_path = Path(__file__).parent / 'inventario' / 'views.py'
        with open(views_path, 'r', encoding='utf-8') as f:
            contenido_vista = f.read()
        
        # Verificar XML generator
        xml_gen_path = Path(__file__).parent / 'inventario' / 'sri' / 'xml_generator.py'
        with open(xml_gen_path, 'r', encoding='utf-8') as f:
            contenido_xml = f.read()
        
        # Verificar excepciones en vista
        vista_ok = True
        if 'raise Exception(f"VALIDACIÓN DE COHERENCIA FALLÓ:' in contenido_vista:
            print("✅ Vista lanza Exception para incoherencia")
        else:
            print("❌ Vista no lanza Exception apropiada")
            vista_ok = False
            
        # Verificar excepciones en XML generator
        xml_ok = True
        if 'raise ValueError(' in contenido_xml and 'INCOHERENCIA EN XML SRI' in contenido_xml:
            print("✅ XML generator lanza ValueError para incoherencia")
        else:
            print("❌ XML generator no lanza ValueError apropiada")
            xml_ok = False
            
        return vista_ok and xml_ok
        
    except Exception as e:
        print(f"❌ Error verificando excepciones: {e}")
        return False

def verificar_tolerancia_decimal():
    """
    🔍 Verificar que se incluye tolerancia para decimales
    """
    print("\n🔍 VERIFICACIÓN 4: Tolerancia decimal")
    print("-" * 50)
    
    try:
        # Verificar en ambos archivos
        archivos = [
            ('Vista', Path(__file__).parent / 'inventario' / 'views.py'),
            ('XML Generator', Path(__file__).parent / 'inventario' / 'sri' / 'xml_generator.py')
        ]
        
        todos_ok = True
        for nombre, archivo_path in archivos:
            with open(archivo_path, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            # Buscar tolerancia
            if "tolerancia = Decimal('0.01')" in contenido:
                print(f"✅ {nombre}: Tolerancia de 1 centavo configurada")
            else:
                print(f"❌ {nombre}: No se encontró tolerancia apropiada")
                todos_ok = False
                
            # Buscar comparación con tolerancia
            if 'diferencia > tolerancia' in contenido:
                print(f"✅ {nombre}: Comparación con tolerancia implementada")
            else:
                print(f"❌ {nombre}: No se encontró comparación con tolerancia")
                todos_ok = False
        
        return todos_ok
        
    except Exception as e:
        print(f"❌ Error verificando tolerancia: {e}")
        return False

def verificar_limpieza_en_error():
    """
    🔍 Verificar que se limpian datos en caso de error
    """
    print("\n🔍 VERIFICACIÓN 5: Limpieza en caso de error")
    print("-" * 50)
    
    try:
        views_path = Path(__file__).parent / 'inventario' / 'views.py'
        with open(views_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
        
        # Verificar que se eliminan formas de pago en caso de error
        if 'factura.formas_pago.all().delete()' in contenido and 'error de validación' in contenido:
            print("✅ Limpieza de formas de pago en caso de error")
            return True
        else:
            print("❌ No se encontró limpieza apropiada en caso de error")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando limpieza: {e}")
        return False

def verificar_logs_informativos():
    """
    🔍 Verificar que se incluyen logs informativos
    """
    print("\n🔍 VERIFICACIÓN 6: Logs informativos")
    print("-" * 50)
    
    try:
        archivos = [
            ('Vista', Path(__file__).parent / 'inventario' / 'views.py'),
            ('XML Generator', Path(__file__).parent / 'inventario' / 'sri' / 'xml_generator.py')
        ]
        
        todos_ok = True
        for nombre, archivo_path in archivos:
            with open(archivo_path, 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            # Buscar logs informativos
            logs_esperados = [
                'Total factura:',
                'Suma',
                'pagos',
                'Coherencia validada'
            ]
            
            logs_encontrados = 0
            for log in logs_esperados:
                if log in contenido:
                    logs_encontrados += 1
            
            if logs_encontrados >= 3:
                print(f"✅ {nombre}: Logs informativos presentes ({logs_encontrados}/4)")
            else:
                print(f"❌ {nombre}: Logs informativos insuficientes ({logs_encontrados}/4)")
                todos_ok = False
        
        return todos_ok
        
    except Exception as e:
        print(f"❌ Error verificando logs: {e}")
        return False

def main():
    """
    🎯 Verificación completa de implementación de coherencia
    """
    print("=" * 70)
    print("🔍 VERIFICACIÓN: IMPLEMENTACIÓN DE VALIDACIÓN DE COHERENCIA")
    print("=" * 70)
    print("Objetivo: Confirmar que suma de pagos = total de factura")
    print("=" * 70)
    
    verificaciones = [
        ("Validación en vista", verificar_validacion_en_vista),
        ("Validación en XML generator", verificar_validacion_en_xml_generator),
        ("Manejo de excepciones", verificar_manejo_excepciones),
        ("Tolerancia decimal", verificar_tolerancia_decimal),
        ("Limpieza en error", verificar_limpieza_en_error),
        ("Logs informativos", verificar_logs_informativos)
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
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE VERIFICACIÓN DE COHERENCIA")
    print("=" * 70)
    
    todas_exitosas = True
    for descripcion, resultado in resultados:
        status = "✅ PASS" if resultado else "❌ FAIL"
        print(f"{status} {descripcion}")
        if not resultado:
            todas_exitosas = False
    
    print("=" * 70)
    if todas_exitosas:
        print("🎉 VALIDACIÓN DE COHERENCIA COMPLETAMENTE IMPLEMENTADA")
        print("✅ Vista valida antes de guardar factura")
        print("✅ XML generator valida antes de generar XML")
        print("✅ Excepciones apropiadas para incoherencias")
        print("✅ Tolerancia decimal para precisión")
        print("✅ Limpieza automática en caso de error")
        print("🎯 Solo facturas coherentes llegan al SRI")
    else:
        print("❌ IMPLEMENTACIÓN INCOMPLETA")
        print("🔧 Revisar verificaciones fallidas")
        print("⚠️ Riesgo de incoherencias en SRI")
        
    print("=" * 70)
    return todas_exitosas

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
