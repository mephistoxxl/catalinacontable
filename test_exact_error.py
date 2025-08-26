#!/usr/bin/env python
"""
Test que simula exactamente el escenario que causa:
"La suma de pagos ($0.56) no coincide con el total de la factura ($0.58)"
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from decimal import Decimal, ROUND_HALF_UP
from inventario.models import Producto, Servicio

def test_escenario_real():
    """
    Simular exactamente el escenario que causa la diferencia de $0.02
    """
    
    print("🔍 SIMULANDO ESCENARIO REAL QUE CAUSA ERROR")
    print("="*60)
    
    # Crear un servicio de prueba que típicamente causa problemas
    # Precio que al ser calculado con IVA da diferencias de redondeo
    precio_problematico = Decimal('0.5178571428571429')  # $0.52 aprox
    iva_code = '2'  # 12% IVA
    
    print(f"📋 DATOS DE PRUEBA:")
    print(f"   Precio base: ${precio_problematico}")
    print(f"   IVA code: {iva_code} (12%)")
    print(f"   Cantidad: 1")
    
    # === SIMULACIÓN JAVASCRIPT (Lo que envía el frontend) ===
    print(f"\n🌐 CÁLCULO JAVASCRIPT:")
    
    precio_js = float(precio_problematico)
    iva_percent_js = 0.12
    cantidad_js = 1
    
    # Algoritmo JavaScript
    precio_con_iva_js = precio_js * (1 + iva_percent_js)
    total_js = cantidad_js * precio_con_iva_js
    
    # Math.round() de JavaScript
    import math
    total_js_redondeado = math.floor(total_js * 100 + 0.5) / 100
    
    print(f"   Precio con IVA: ${precio_con_iva_js}")
    print(f"   Total sin redondear: ${total_js}")
    print(f"   Total CON Math.round(): ${total_js_redondeado}")
    
    # === SIMULACIÓN BACKEND DJANGO (ALGORITMO ACTUAL) ===
    print(f"\n🐍 CÁLCULO DJANGO BACKEND:")
    
    iva_percent_django = Decimal('0.12')
    cantidad_django = 1
    
    # Algoritmo Django NUEVO (que implementamos)
    precio_con_iva_unitario = precio_problematico * (Decimal('1.00') + iva_percent_django)
    total_django = precio_con_iva_unitario * cantidad_django
    subtotal_django = precio_problematico * cantidad_django
    valor_iva_django = total_django - subtotal_django
    
    # Redondeo Django
    PRECISION_DOS_DECIMALES = Decimal('0.01')
    total_django_redondeado = total_django.quantize(PRECISION_DOS_DECIMALES, rounding=ROUND_HALF_UP)
    
    print(f"   Precio con IVA unitario: ${precio_con_iva_unitario}")
    print(f"   Total sin redondear: ${total_django}")
    print(f"   Total CON redondeo Django: ${total_django_redondeado}")
    
    # === COMPARACIÓN ===
    diferencia = abs(total_js_redondeado - float(total_django_redondeado))
    
    print(f"\n📊 COMPARACIÓN:")
    print(f"   JavaScript: ${total_js_redondeado}")
    print(f"   Django:     ${float(total_django_redondeado)}")
    print(f"   Diferencia: ${diferencia:.4f}")
    
    if diferencia >= 0.01:
        print("   ❌ PROBLEMA: Diferencia >= $0.01 - ESTO CAUSA EL ERROR")
    else:
        print("   ✅ CORRECTO: Diferencia < $0.01")
    
    # === SIMULAR MÚLTIPLES PRODUCTOS QUE SUMEN $0.56 vs $0.58 ===
    print(f"\n🔍 CASO ESPECÍFICO: Productos que sumen $0.56 vs $0.58")
    
    # Posibles combinaciones que den esa diferencia exacta
    casos_problematicos = [
        # [precio, cantidad, descripcion]
        [Decimal('0.2589'), 2, "Servicio A x2"],
        [Decimal('0.1724'), 3, "Servicio B x3"], 
        [Decimal('0.5172'), 1, "Servicio C x1"],
    ]
    
    for precio, cantidad, desc in casos_problematicos:
        print(f"\n   🧪 CASO: {desc}")
        
        # JavaScript
        precio_js = float(precio)
        total_js = math.floor((precio_js * 1.12 * cantidad) * 100 + 0.5) / 100
        
        # Django  
        total_django = (precio * (Decimal('1.12')) * cantidad).quantize(PRECISION_DOS_DECIMALES, rounding=ROUND_HALF_UP)
        
        diff = abs(total_js - float(total_django))
        print(f"      JS: ${total_js:.2f}, Django: ${float(total_django):.2f}, Diff: ${diff:.4f}")
        
        if diff >= 0.02:
            print(f"      ⚠️  ESTE CASO PUEDE CAUSAR LA DIFERENCIA DE $0.02!")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_escenario_real()
