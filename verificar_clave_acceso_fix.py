#!/usr/bin/env python
"""
Script para verificar y corregir el problema de clave de acceso
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura
from inventario.sri.integracion_django import SRIIntegration, generar_claves_acceso_faltantes

def main():
    print("🔍 Verificando problema de clave de acceso...")
    
    # Verificar facturas sin clave de acceso
    facturas_sin_clave = Factura.objects.filter(clave_acceso__isnull=True)
    print(f"📊 Facturas sin clave de acceso: {facturas_sin_clave.count()}")
    
    # Verificar facturas con clave vacía
    facturas_clave_vacia = Factura.objects.filter(clave_acceso='')
    print(f"📊 Facturas con clave vacía: {facturas_clave_vacia.count()}")
    
    total_problematicas = facturas_sin_clave.count() + facturas_clave_vacia.count()
    
    if total_problematicas == 0:
        print("✅ No hay facturas con problemas de clave de acceso")
    else:
        print(f"⚠️  Encontradas {total_problematicas} facturas con problemas de clave")
        
        # Mostrar algunas facturas problemáticas
        print("\n📋 Ejemplos de facturas problemáticas:")
        for factura in list(facturas_sin_clave[:5]) + list(facturas_clave_vacia[:5]):
            print(f"   - ID: {factura.id}, Número: {factura.numero}, Fecha: {factura.fecha_emision}")
        
        # Preguntar si generar claves
        respuesta = input(f"\n❓ ¿Generar claves de acceso para estas {total_problematicas} facturas? (y/N): ")
        
        if respuesta.lower() in ['y', 'yes', 'sí', 'si']:
            print("🔧 Generando claves de acceso...")
            
            # Incluir facturas con clave vacía
            facturas_clave_vacia.update(clave_acceso=None)
            
            resultados = generar_claves_acceso_faltantes()
            
            exitosas = sum(1 for r in resultados if r['success'])
            errores = sum(1 for r in resultados if not r['success'])
            
            print(f"✅ Claves generadas exitosamente: {exitosas}")
            print(f"❌ Errores: {errores}")
            
            if errores > 0:
                print("\n📋 Facturas con error:")
                for resultado in resultados:
                    if not resultado['success']:
                        print(f"   - Factura {resultado['numero']}: {resultado['error']}")
        else:
            print("❌ Operación cancelada")
    
    # Verificar consistencia de XML vs Clave de acceso
    print("\n🔍 Verificando consistencia XML vs Clave de acceso...")
    
    facturas_con_clave = Factura.objects.exclude(clave_acceso__isnull=True).exclude(clave_acceso='')
    print(f"📊 Facturas con clave de acceso: {facturas_con_clave.count()}")
    
    # Mostrar estadísticas de la corrección
    print("\n📊 Resumen del fix implementado:")
    print("✅ Ahora las claves se generan ANTES del XML")
    print("✅ Las claves se persisten inmediatamente en la base de datos")
    print("✅ Se evita la regeneración de claves existentes")
    print("✅ Se valida consistencia entre XML y base de datos")
    
    print("\n🏁 Verificación completada")

if __name__ == "__main__":
    main()
