#!/usr/bin/env python
"""
Test para verificar que los cálculos de JavaScript y Django dan el mismo resultado
"""

from decimal import Decimal, ROUND_HALF_UP
import math

def test_javascript_vs_django():
    """Simular el cálculo exacto que hace JavaScript vs Django"""
    
    # Casos de prueba con valores reales que pueden dar $0.02 de diferencia
    casos_prueba = [
        # [precio_unitario, cantidad, iva_percent]
        [0.467, 1, 0.12],  # Caso típico servicios
        [0.189, 3, 0.12],  # Otro caso problemático  
        [0.234, 2, 0.15],  # Con 15% IVA
        [0.156, 4, 0.12],  # Cantidad múltiple
    ]
    
    print("🔢 COMPARACIÓN JAVASCRIPT VS DJANGO")
    print("="*60)
    
    for precio, cantidad, iva_percent in casos_prueba:
        print(f"\n📊 CASO: Precio=${precio}, Cantidad={cantidad}, IVA={iva_percent*100}%")
        
        # ===== SIMULACIÓN JAVASCRIPT =====
        precio_con_iva_js = precio * (1 + iva_percent)
        total_con_iva_js = cantidad * precio_con_iva_js
        
        # Redondeo JavaScript Math.round()
        precio_con_iva_js_redondeado = round(precio_con_iva_js * 100) / 100
        total_con_iva_js_redondeado = round(total_con_iva_js * 100) / 100
        
        # ===== SIMULACIÓN DJANGO (NUEVO ALGORITMO) =====
        precio_unitario_decimal = Decimal(str(precio))
        iva_percent_decimal = Decimal(str(iva_percent))
        cantidad_decimal = Decimal(str(cantidad))
        
        # Nuevo algoritmo Django (igual que JavaScript)
        precio_con_iva_django = precio_unitario_decimal * (Decimal('1.00') + iva_percent_decimal)
        total_django = precio_con_iva_django * cantidad_decimal
        subtotal_django = precio_unitario_decimal * cantidad_decimal
        valor_iva_django = total_django - subtotal_django

        # Redondeo Django
        subtotal_django = subtotal_django.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        valor_iva_django = valor_iva_django.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_django = total_django.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Comparar resultados
        diferencia = abs(float(total_django) - total_con_iva_js_redondeado)
        
        print(f"   JavaScript: ${total_con_iva_js_redondeado:.2f}")
        print(f"   Django:     ${float(total_django):.2f}")
        print(f"   Diferencia: ${diferencia:.2f}")
        
        if diferencia < 0.01:
            print("   ✅ CORRECTO: Sin diferencia significativa")
        else:
            print("   ❌ ERROR: Diferencia > $0.01")
            
    print("\n" + "="*60)
    print("🎯 RESULTADO: Si todos los casos muestran ✅, el problema está solucionado")

if __name__ == "__main__":
    test_javascript_vs_django()
