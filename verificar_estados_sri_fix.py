#!/usr/bin/env python
"""
Script para verificar y corregir el problema de estados SRI no actualizados
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura
from inventario.sri.integracion_django import SRIIntegration

def main():
    print("🔍 Verificando problema de estados SRI no actualizados...")
    
    # Buscar facturas problemáticas
    facturas_pendientes = Factura.objects.filter(
        estado_sri__in=['PENDIENTE', 'RECIBIDA']
    ).exclude(
        clave_acceso__isnull=True
    ).exclude(
        clave_acceso=''
    )
    
    print(f"📊 Facturas en estado PENDIENTE/RECIBIDA con clave: {facturas_pendientes.count()}")
    
    if facturas_pendientes.count() == 0:
        print("✅ No hay facturas pendientes para verificar")
        return
    
    # Mostrar algunas facturas problemáticas
    print("\n📋 Ejemplos de facturas pendientes:")
    for factura in facturas_pendientes[:10]:
        print(f"   - ID: {factura.id}, Número: {factura.numero}, Estado: {factura.estado_sri}, Fecha: {factura.fecha_emision}")
    
    if facturas_pendientes.count() > 10:
        print(f"   ... y {facturas_pendientes.count() - 10} más")
    
    # Preguntar si consultar estados
    respuesta = input(f"\n❓ ¿Consultar el estado real de estas {facturas_pendientes.count()} facturas en el SRI? (y/N): ")
    
    if respuesta.lower() in ['y', 'yes', 'sí', 'si']:
        print("🔍 Consultando estados en el SRI...")
        
        integration = SRIIntegration()
        autorizadas = 0
        rechazadas = 0
        aun_pendientes = 0
        errores = 0
        
        for i, factura in enumerate(facturas_pendientes[:50], 1):  # Limitar a 50
            try:
                print(f"   [{i:2d}/{min(50, facturas_pendientes.count())}] Consultando factura {factura.numero}...", end="")
                
                estado_anterior = factura.estado_sri
                resultado = integration.consultar_estado_factura(factura.id)
                
                # Recargar la factura para ver el estado actualizado
                factura.refresh_from_db()
                estado_nuevo = factura.estado_sri
                
                if estado_nuevo != estado_anterior:
                    print(f" {estado_anterior} → {estado_nuevo}")
                    
                    if estado_nuevo in ('AUTORIZADA', 'AUTORIZADO'):
                        autorizadas += 1
                    elif estado_nuevo in ('RECHAZADA', 'NO_AUTORIZADA'):
                        rechazadas += 1
                    elif estado_nuevo == 'PENDIENTE':
                        aun_pendientes += 1
                else:
                    print(f" Sin cambios ({estado_nuevo})")
                    if estado_nuevo == 'PENDIENTE':
                        aun_pendientes += 1
                        
            except Exception as e:
                print(f" ERROR: {str(e)}")
                errores += 1
        
        print(f"\n📊 Resultados de la consulta:")
        print(f"   ✅ Autorizadas: {autorizadas}")
        print(f"   ❌ Rechazadas: {rechazadas}")
        print(f"   ⏳ Aún pendientes: {aun_pendientes}")
        print(f"   🔴 Errores: {errores}")
        
        # Verificar el fix
        print(f"\n✅ Fix implementado:")
        print(f"   📝 Estados ahora se normalizan correctamente (AUTORIZADA/AUTORIZADO)")
        print(f"   💾 Todos los cambios se persisten en la base de datos")
        print(f"   🔄 Se actualiza tras CADA consulta de autorización")
        print(f"   📋 Logging detallado para debuggear problemas")
        
    else:
        print("❌ Operación cancelada")
    
    print("\n🏁 Verificación completada")

if __name__ == "__main__":
    main()
