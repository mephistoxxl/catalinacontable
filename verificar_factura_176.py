#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script rápido para consultar el estado de la factura #176
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sisfact.settings')
django.setup()

from inventario.models import Factura

def verificar_factura_176():
    try:
        factura = Factura.objects.get(id=176)
        print(f"📄 FACTURA #{factura.id}:")
        print(f"   Cliente ID: {factura.cliente.identificacion}")
        print(f"   Fecha: {factura.fecha_emision}")
        print(f"   Estado SRI: '{factura.estado_sri}'")
        print(f"   Clave de Acceso: '{factura.clave_acceso}'")
        print(f"   Número de Autorización: '{factura.numero_autorizacion}'")
        print(f"   Fecha de Autorización: '{factura.fecha_autorizacion}'")
        print(f"   Total: ${factura.monto_general}")
        
        # Verificar qué condición cumple
        print(f"\n🔍 ANÁLISIS DE CONDICIONES:")
        print(f"   ✓ Tiene numero_autorizacion: {bool(factura.numero_autorizacion and factura.numero_autorizacion.strip())}")
        print(f"   ✓ Tiene fecha_autorizacion: {bool(factura.fecha_autorizacion)}")
        print(f"   ✓ Estado es AUTORIZADA: {factura.estado_sri in ['AUTORIZADA', 'AUTORIZADO']}")
        
        # Simular la lógica del template
        if factura.numero_autorizacion and factura.fecha_autorizacion:
            print(f"   🎯 TEMPLATE MOSTRARÍA: ✅ Autorizada SRI")
        elif factura.estado_sri in ['AUTORIZADA', 'AUTORIZADO']:
            if factura.numero_autorizacion:
                print(f"   🎯 TEMPLATE MOSTRARÍA: ✅ Autorizada SRI")
            else:
                print(f"   🎯 TEMPLATE MOSTRARÍA: ⚠️ Estado Inconsistente")
        else:
            print(f"   🎯 TEMPLATE MOSTRARÍA: Estado {factura.estado_sri}")
            
    except Factura.DoesNotExist:
        print("❌ Factura #176 no encontrada")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    verificar_factura_176()
