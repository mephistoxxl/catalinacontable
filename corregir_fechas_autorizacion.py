#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para corregir facturas autorizadas que no tienen fecha de autorización.
"""

import os
import sys
import django
from datetime import datetime

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sisfact.settings')
django.setup()

from inventario.models import Factura
from django.utils import timezone

def corregir_fechas_autorizacion():
    """
    Encuentra facturas autorizadas que no tienen fecha de autorización
    y les asigna una fecha basándose en información disponible.
    """
    print("🔍 Buscando facturas autorizadas sin fecha de autorización...")
    
    # Buscar facturas autorizadas sin fecha
    facturas_sin_fecha = Factura.objects.filter(
        estado_sri='AUTORIZADA',
        numero_autorizacion__isnull=False,
        fecha_autorizacion__isnull=True
    ).exclude(numero_autorizacion='')
    
    total = facturas_sin_fecha.count()
    print(f"📊 Se encontraron {total} facturas que necesitan corrección")
    
    if total == 0:
        print("✅ No hay facturas para corregir")
        return
    
    corregidas = 0
    errores = 0
    
    for factura in facturas_sin_fecha:
        try:
            print(f"🔧 Corrigiendo Factura #{factura.id}...")
            
            # Usar fecha de emisión como base, o fecha actual si no está disponible
            if factura.fecha_emision:
                # Usar la fecha de emisión como fecha de autorización aproximada
                factura.fecha_autorizacion = timezone.make_aware(
                    datetime.combine(factura.fecha_emision, datetime.min.time())
                )
                print(f"   ✓ Usando fecha de emisión: {factura.fecha_emision}")
            else:
                # Usar fecha actual si no hay fecha de emisión
                factura.fecha_autorizacion = timezone.now()
                print(f"   ✓ Usando fecha actual")
            
            factura.save()
            corregidas += 1
            print(f"   ✅ Factura #{factura.id} corregida exitosamente")
            
        except Exception as e:
            errores += 1
            print(f"   ❌ Error corrigiendo factura #{factura.id}: {str(e)}")
            continue
    
    print(f"\n🎉 RESUMEN:")
    print(f"   ✅ Facturas corregidas: {corregidas}")
    print(f"   ❌ Errores: {errores}")
    print(f"   📊 Total procesadas: {total}")
    
    if corregidas > 0:
        print(f"\n💡 Las facturas corregidas ahora aparecerán como '✅ Autorizada SRI' en la lista")

if __name__ == "__main__":
    corregir_fechas_autorizacion()
