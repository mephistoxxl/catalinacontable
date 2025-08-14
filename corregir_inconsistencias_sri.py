#!/usr/bin/env python
"""
Script para corregir inconsistencias de estado SRI
Identifica facturas que tienen estado_sri='AUTORIZADA' sin autorización real del SRI
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura

def corregir_inconsistencias_sri():
    """Corregir estados inconsistentes en facturas"""
    print("🔍 BÚSQUEDA DE INCONSISTENCIAS EN ESTADOS SRI")
    print("=" * 60)
    
    # Buscar facturas con estado AUTORIZADA/AUTORIZADO pero sin autorización real
    facturas_inconsistentes = Factura.objects.filter(
        estado_sri__in=['AUTORIZADA', 'AUTORIZADO'],
        numero_autorizacion__isnull=True,
        fecha_autorizacion__isnull=True
    )
    
    print(f"\n📊 FACTURAS CON ESTADO INCONSISTENTE: {facturas_inconsistentes.count()}")
    
    if facturas_inconsistentes.count() > 0:
        print("\nFacturas encontradas:")
        for factura in facturas_inconsistentes:
            print(f"  ID {factura.id}: Estado='{factura.estado_sri}', Cliente={factura.cliente.identificacion}, Fecha={factura.fecha_emision}")
            print(f"    Núm. Autorización: {factura.numero_autorizacion}")
            print(f"    Fecha Autorización: {factura.fecha_autorizacion}")
            print(f"    Clave Acceso: {factura.clave_acceso}")
            print()
        
        respuesta = input("¿Corregir estos estados a 'PENDIENTE'? (s/N): ").lower().strip()
        
        if respuesta == 's':
            count = 0
            for factura in facturas_inconsistentes:
                estado_anterior = factura.estado_sri
                factura.estado_sri = 'PENDIENTE'
                factura.save(update_fields=['estado_sri'])
                print(f"  ✅ Factura {factura.id}: {estado_anterior} → PENDIENTE")
                count += 1
            
            print(f"\n✅ Se corrigieron {count} facturas")
        else:
            print("\n❌ No se realizaron cambios")
    else:
        print("✅ No se encontraron inconsistencias")
    
    # Verificar facturas que SÍ tienen autorización real
    facturas_autorizadas = Factura.objects.filter(
        numero_autorizacion__isnull=False,
        fecha_autorizacion__isnull=False
    ).exclude(
        estado_sri__in=['AUTORIZADA', 'AUTORIZADO']
    )
    
    print(f"\n📊 FACTURAS CON AUTORIZACIÓN PERO ESTADO INCORRECTO: {facturas_autorizadas.count()}")
    
    if facturas_autorizadas.count() > 0:
        print("\nFacturas que deberían estar AUTORIZADAS:")
        for factura in facturas_autorizadas:
            print(f"  ID {factura.id}: Estado='{factura.estado_sri}', Autorización={factura.numero_autorizacion}")
        
        respuesta = input("¿Corregir estos estados a 'AUTORIZADA'? (s/N): ").lower().strip()
        
        if respuesta == 's':
            count = 0
            for factura in facturas_autorizadas:
                estado_anterior = factura.estado_sri
                factura.estado_sri = 'AUTORIZADA'
                factura.save(update_fields=['estado_sri'])
                print(f"  ✅ Factura {factura.id}: {estado_anterior} → AUTORIZADA")
                count += 1
            
            print(f"\n✅ Se corrigieron {count} facturas")
        else:
            print("\n❌ No se realizaron cambios")
    
    print("\n🎯 RESUMEN FINAL:")
    
    # Estadísticas finales
    stats = {}
    for estado in ['AUTORIZADA', 'AUTORIZADO', 'PENDIENTE', 'RECHAZADA', 'ERROR', 'RECIBIDA']:
        count = Factura.objects.filter(estado_sri=estado).count()
        if count > 0:
            stats[estado] = count
    
    print("  Estados actuales en BD:")
    for estado, count in stats.items():
        print(f"    {estado}: {count} facturas")
    
    # Verificar consistencia final
    correctas = Factura.objects.filter(
        estado_sri__in=['AUTORIZADA', 'AUTORIZADO'],
        numero_autorizacion__isnull=False,
        fecha_autorizacion__isnull=False
    ).count()
    
    inconsistentes = Factura.objects.filter(
        estado_sri__in=['AUTORIZADA', 'AUTORIZADO'],
        numero_autorizacion__isnull=True,
        fecha_autorizacion__isnull=True
    ).count()
    
    print(f"\n  ✅ Facturas AUTORIZADAS consistentes: {correctas}")
    print(f"  ⚠️  Facturas AUTORIZADAS inconsistentes: {inconsistentes}")
    
    if inconsistentes == 0:
        print("\n🎉 ¡TODAS LAS INCONSISTENCIAS HAN SIDO CORREGIDAS!")
    else:
        print(f"\n⚠️  Aún quedan {inconsistentes} inconsistencias por resolver")

if __name__ == "__main__":
    corregir_inconsistencias_sri()
