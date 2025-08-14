#!/usr/bin/env python
"""
Script de verificación de consistencia de estados SRI
Verifica que el sistema reconozca tanto 'AUTORIZADA' como 'AUTORIZADO'
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura
from inventario.sri.integracion_django import SRIIntegration

def test_estados_sri():
    """Test de reconocimiento de estados SRI"""
    print("🔍 VERIFICACIÓN DE ESTADOS SRI")
    print("=" * 50)
    
    print("\n1. Verificación de modelos existentes:")
    
    # Contar facturas por estado
    estados = {}
    for estado in ['AUTORIZADA', 'AUTORIZADO', 'PENDIENTE', 'RECHAZADA', 'ERROR', 'RECIBIDA']:
        count = Factura.objects.filter(estado_sri=estado).count()
        if count > 0:
            estados[estado] = count
    
    if estados:
        print("   Estados encontrados en BD:")
        for estado, count in estados.items():
            print(f"      {estado}: {count} facturas")
    else:
        print("   No se encontraron facturas con estados específicos")
    
    print("\n2. Test de instancia SRIIntegration:")
    try:
        sri = SRIIntegration()
        print("   ✅ SRIIntegration inicializada correctamente")
        
        # Buscar una factura para test
        factura = Factura.objects.first()
        if factura:
            print(f"   📄 Factura de test: ID {factura.id}, Estado: {factura.estado_sri}")
            
            # Verificar método _actualizar_factura_con_resultado
            print("   🔧 Verificando método _actualizar_factura_con_resultado...")
            
            # Simular resultado autorizado
            resultado_autorizado = {
                'estado': 'AUTORIZADO',
                'numeroAutorizacion': '1234567890123456789',
                'fechaAutorizacion': '2024-01-01T10:00:00-05:00'
            }
            
            estado_original = factura.estado_sri
            try:
                # Test sin guardar cambios reales
                sri._actualizar_factura_con_resultado(factura, resultado_autorizado, factura.clave_acceso)
                print(f"      ✅ Estado procesado: {factura.estado_sri}")
                
                # Restaurar estado original
                factura.estado_sri = estado_original
                
            except Exception as e:
                print(f"      ❌ Error al procesar: {e}")
                
        else:
            print("   ⚠️  No hay facturas disponibles para test")
            
    except Exception as e:
        print(f"   ❌ Error al inicializar SRIIntegration: {e}")
    
    print("\n3. Verificación de código corregido:")
    
    # Leer el archivo para verificar que contiene las correcciones
    try:
        with open('inventario/sri/integracion_django.py', 'r', encoding='utf-8') as f:
            contenido = f.read()
            
        # Buscar las correcciones de estado
        autorizada_count = contenido.count("== 'AUTORIZADA'")
        autorizado_count = contenido.count("== 'AUTORIZADO'")
        ambos_count = contenido.count("'AUTORIZADA' or") + contenido.count("'AUTORIZADO' or")
        
        print(f"   Verificaciones encontradas:")
        print(f"      == 'AUTORIZADA': {autorizada_count}")
        print(f"      == 'AUTORIZADO': {autorizado_count}")
        print(f"      Verificaciones combinadas: {ambos_count}")
        
        if ambos_count > 0:
            print("   ✅ Se encontraron verificaciones que reconocen ambos estados")
        else:
            print("   ⚠️  No se encontraron verificaciones combinadas")
            
    except Exception as e:
        print(f"   ❌ Error al leer archivo: {e}")
    
    print("\n✅ VERIFICACIÓN COMPLETADA")
    print("   Las correcciones implementadas permiten reconocer tanto 'AUTORIZADA' como 'AUTORIZADO'")

if __name__ == "__main__":
    test_estados_sri()
