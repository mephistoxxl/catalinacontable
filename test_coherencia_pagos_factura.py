#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔍 PRUEBA: Validación de coherencia entre formas de pago y total de factura

Esta prueba verifica que:
1. ✅ Se valida que la suma de pagos = total de factura
2. ❌ Se rechaza cuando hay incoherencia
3. ✅ La validación funciona en vista y XML generator
4. 🎯 Solo facturas coherentes llegan al SRI
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura, FormaPago, Caja
from inventario.sri.xml_generator import SRIXMLGenerator
from decimal import Decimal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_coherencia_exacta():
    """
    🟢 Prueba 1: Pagos que suman exactamente el total de la factura
    """
    print("🟢 PRUEBA 1: Coherencia exacta - pagos = total factura")
    print("-" * 60)
    
    try:
        # Buscar una factura de prueba
        factura = Factura.objects.first()
        if not factura:
            print("❌ No hay facturas para probar")
            return False
            
        # Limpiar formas de pago existentes
        FormaPago.objects.filter(factura=factura).delete()
        
        # Configurar total de factura
        total_factura = Decimal('100.00')
        factura.monto_general = total_factura
        factura.save()
        
        print(f"📋 Factura ID: {factura.id}, Total: ${total_factura}")
        
        # Crear formas de pago que sumen exactamente el total
        caja = Caja.objects.filter(activo=True).first()
        if not caja:
            print("❌ No hay cajas activas")
            return False
        
        # Crear 2 pagos que sumen exactamente 100.00
        pago1 = FormaPago.objects.create(
            factura=factura,
            forma_pago='01',  # Efectivo
            caja=caja,
            total=Decimal('60.00')
        )
        
        pago2 = FormaPago.objects.create(
            factura=factura,
            forma_pago='16',  # Tarjeta débito
            caja=caja,
            total=Decimal('40.00')
        )
        
        print(f"💰 Pago 1: ${pago1.total} (Código: {pago1.forma_pago})")
        print(f"💰 Pago 2: ${pago2.total} (Código: {pago2.forma_pago})")
        print(f"💰 Suma total: ${pago1.total + pago2.total}")
        
        # Probar generación XML (debería pasar)
        xml_generator = SRIXMLGenerator()
        try:
            xml_content = xml_generator.generar_xml_factura(factura)
            print("✅ XML generado exitosamente - coherencia validada")
            
            # Verificar que el XML contiene ambos pagos
            if f'<total>{pago1.total}</total>' in xml_content and f'<total>{pago2.total}</total>' in xml_content:
                print("✅ XML contiene ambos pagos correctamente")
                return True
            else:
                print("❌ XML no contiene los pagos esperados")
                return False
                
        except Exception as e:
            print(f"❌ Error inesperado generando XML: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error en prueba de coherencia exacta: {e}")
        return False
        
    finally:
        # Limpiar
        try:
            FormaPago.objects.filter(factura=factura).delete()
        except:
            pass

def test_incoherencia_detectada():
    """
    🔴 Prueba 2: Pagos que NO suman el total de la factura (debe fallar)
    """
    print("\n🔴 PRUEBA 2: Incoherencia detectada - pagos ≠ total factura")
    print("-" * 60)
    
    try:
        # Buscar una factura de prueba
        factura = Factura.objects.first()
        if not factura:
            print("❌ No hay facturas para probar")
            return False
            
        # Limpiar formas de pago existentes
        FormaPago.objects.filter(factura=factura).delete()
        
        # Configurar total de factura
        total_factura = Decimal('100.00')
        factura.monto_general = total_factura
        factura.save()
        
        print(f"📋 Factura ID: {factura.id}, Total: ${total_factura}")
        
        # Crear formas de pago que NO sumen el total (diferencia significativa)
        caja = Caja.objects.filter(activo=True).first()
        if not caja:
            print("❌ No hay cajas activas")
            return False
        
        # Crear pagos que sumen solo 85.00 (diferencia de 15.00)
        pago1 = FormaPago.objects.create(
            factura=factura,
            forma_pago='01',  # Efectivo
            caja=caja,
            total=Decimal('50.00')
        )
        
        pago2 = FormaPago.objects.create(
            factura=factura,
            forma_pago='16',  # Tarjeta débito
            caja=caja,
            total=Decimal('35.00')
        )
        
        print(f"💰 Pago 1: ${pago1.total} (Código: {pago1.forma_pago})")
        print(f"💰 Pago 2: ${pago2.total} (Código: {pago2.forma_pago})")
        print(f"💰 Suma total: ${pago1.total + pago2.total}")
        print(f"⚠️ Diferencia: ${total_factura - (pago1.total + pago2.total)}")
        
        # Probar generación XML (debería FALLAR)
        xml_generator = SRIXMLGenerator()
        try:
            xml_content = xml_generator.generar_xml_factura(factura)
            print("❌ ERROR: XML generado a pesar de incoherencia")
            return False
            
        except ValueError as e:
            if "INCOHERENCIA EN XML SRI" in str(e):
                print("✅ CORRECTO: Incoherencia detectada y rechazada")
                print(f"✅ Mensaje de error: {str(e)[:100]}...")
                return True
            else:
                print(f"❌ Error incorrecto: {str(e)[:100]}...")
                return False
                
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error en prueba de incoherencia: {e}")
        return False
        
    finally:
        # Limpiar
        try:
            FormaPago.objects.filter(factura=factura).delete()
        except:
            pass

def test_tolerancia_decimal():
    """
    🟡 Prueba 3: Diferencia mínima dentro de tolerancia (debe pasar)
    """
    print("\n🟡 PRUEBA 3: Tolerancia decimal - diferencia < 1 centavo")
    print("-" * 60)
    
    try:
        # Buscar una factura de prueba
        factura = Factura.objects.first()
        if not factura:
            print("❌ No hay facturas para probar")
            return False
            
        # Limpiar formas de pago existentes
        FormaPago.objects.filter(factura=factura).delete()
        
        # Configurar total de factura
        total_factura = Decimal('100.00')
        factura.monto_general = total_factura
        factura.save()
        
        print(f"📋 Factura ID: {factura.id}, Total: ${total_factura}")
        
        # Crear formas de pago con diferencia mínima (0.005 = medio centavo)
        caja = Caja.objects.filter(activo=True).first()
        if not caja:
            print("❌ No hay cajas activas")
            return False
        
        # Crear pagos que sumen 99.995 (diferencia de 0.005)
        pago1 = FormaPago.objects.create(
            factura=factura,
            forma_pago='01',  # Efectivo
            caja=caja,
            total=Decimal('60.000')
        )
        
        pago2 = FormaPago.objects.create(
            factura=factura,
            forma_pago='16',  # Tarjeta débito
            caja=caja,
            total=Decimal('39.995')
        )
        
        suma_pagos = pago1.total + pago2.total
        diferencia = abs(total_factura - suma_pagos)
        
        print(f"💰 Pago 1: ${pago1.total}")
        print(f"💰 Pago 2: ${pago2.total}")
        print(f"💰 Suma total: ${suma_pagos}")
        print(f"🔍 Diferencia: ${diferencia} (< 0.01 = dentro de tolerancia)")
        
        # Probar generación XML (debería pasar por tolerancia)
        xml_generator = SRIXMLGenerator()
        try:
            xml_content = xml_generator.generar_xml_factura(factura)
            print("✅ XML generado exitosamente - tolerancia aplicada")
            return True
            
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error en prueba de tolerancia: {e}")
        return False
        
    finally:
        # Limpiar
        try:
            FormaPago.objects.filter(factura=factura).delete()
        except:
            pass

def main():
    """
    🎯 Función principal de pruebas de coherencia
    """
    print("=" * 70)
    print("🔍 PRUEBA: VALIDACIÓN DE COHERENCIA PAGOS vs TOTAL FACTURA")
    print("=" * 70)
    print("Objetivo: Verificar que suma de pagos = total de factura")
    print("=" * 70)
    
    pruebas = [
        ("Coherencia exacta", test_coherencia_exacta),
        ("Incoherencia detectada", test_incoherencia_detectada),
        ("Tolerancia decimal", test_tolerancia_decimal)
    ]
    
    resultados = []
    
    for nombre, prueba in pruebas:
        try:
            resultado = prueba()
            resultados.append((nombre, resultado))
        except Exception as e:
            print(f"❌ Error en prueba '{nombre}': {e}")
            resultados.append((nombre, False))
    
    # Resumen
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE PRUEBAS DE COHERENCIA")
    print("=" * 70)
    
    todas_exitosas = True
    for descripcion, resultado in resultados:
        status = "✅ PASS" if resultado else "❌ FAIL"
        print(f"{status} {descripcion}")
        if not resultado:
            todas_exitosas = False
    
    print("=" * 70)
    if todas_exitosas:
        print("🎉 TODAS LAS PRUEBAS DE COHERENCIA PASARON")
        print("✅ Validación funciona correctamente")
        print("✅ Facturas coherentes pasan")
        print("✅ Facturas incoherentes son rechazadas")
        print("✅ Tolerancia decimal funciona")
        print("🎯 Solo datos coherentes llegan al SRI")
    else:
        print("❌ ALGUNAS PRUEBAS FALLARON")
        print("🔧 Revisar implementación de validación")
        
    print("=" * 70)
    return todas_exitosas

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
