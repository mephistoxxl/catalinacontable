#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de debug para verificar datos de formas de pago
"""

print("=== INSTRUCCIONES DE DEBUG ===")
print()
print("1. Abre Chrome/Edge en modo desarrollador (F12)")
print("2. Ve a la pestaña 'Console'")
print("3. Carga la página de crear factura")
print("4. Agrega un producto")
print("5. En la sección 'Formas de Pago':")
print("   a) Haz clic en 'Efectivo'")
print("   b) Selecciona una caja")
print("   c) Ingresa el monto (debería auto-completarse)")
print("   d) Haz clic en 'Confirmar Pago'")
print("6. Antes de enviar, ejecuta en la consola:")
print()
print("   console.log('DEBUG: pagosEfectivo array:', pagosEfectivo);")
print("   console.log('DEBUG: Campo input:', document.getElementById('pagos_efectivo_input').value);")
print()
print("7. Luego envía el formulario")
print("8. Verifica en el terminal del servidor los mensajes que empiecen con '📦'")
print()
print("=== QUÉ VERIFICAR ===")
print("- Si pagosEfectivo está vacío: No agregaste pagos correctamente")
print("- Si el campo input está vacío: El JavaScript no está funcionando")
print("- Si los datos '📦' no aparecen: El formulario no se está enviando")
print()
print("¿Quieres que ejecute algún test específico? (Y/N)")

# Opcional: Test de la base de datos
import os
import sys
import django

# Solo ejecutar si estamos en el directorio correcto
if os.path.exists('manage.py'):
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
    
    try:
        django.setup()
        from inventario.models import Caja
        
        print("=== TEST DE CAJAS DISPONIBLES ===")
        cajas = Caja.objects.filter(activo=True)
        print(f"Cajas activas encontradas: {cajas.count()}")
        for caja in cajas:
            print(f"  - ID: {caja.id}, Descripción: {caja.descripcion}")
            
        if cajas.count() == 0:
            print("❌ NO HAY CAJAS ACTIVAS - Esto podría causar problemas")
        else:
            print("✅ Hay cajas disponibles para seleccionar")
            
    except Exception as e:
        print(f"Error en test de Django: {e}")
else:
    print("Ejecutar desde el directorio raíz del proyecto Django")
