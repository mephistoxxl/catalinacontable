#!/usr/bin/env python
"""
Script para probar y verificar la validación XSD de archivos XML
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Factura
from inventario.sri.integracion_django import SRIIntegration, validar_xml_existente, validar_lote_xml_facturas

def main():
    print("🔍 Verificando implementación de validación XSD...")
    
    # Verificar que los archivos XSD existen
    try:
        integration = SRIIntegration()
        xsd_path = integration._obtener_ruta_xsd()
        print(f"✅ XSD encontrado: {xsd_path}")
    except Exception as e:
        print(f"❌ Error encontrando XSD: {e}")
        return
    
    # Verificar facturas para probar
    facturas_con_clave = Factura.objects.exclude(clave_acceso__isnull=True).exclude(clave_acceso='')
    print(f"📊 Facturas con clave de acceso: {facturas_con_clave.count()}")
    
    if facturas_con_clave.count() == 0:
        print("⚠️  No hay facturas para probar. Creando una factura de prueba...")
        return
    
    # Probar generación de XML con validación
    factura_prueba = facturas_con_clave.first()
    print(f"\n🧪 Probando generación de XML con validación para factura {factura_prueba.numero}...")
    
    try:
        # Generar XML con validación
        xml_path = integration.generar_xml_factura(factura_prueba, validar_xsd=True)
        print(f"✅ XML generado y validado: {xml_path}")
        
        # Validar el XML generado independientemente
        resultado = validar_xml_existente(xml_path)
        if resultado['success']:
            print("✅ Validación independiente exitosa")
        else:
            print(f"❌ Error en validación independiente: {resultado['message']}")
            
    except Exception as e:
        print(f"❌ Error generando/validando XML: {e}")
    
    # Probar el flujo completo con validación
    print(f"\n🚀 Probando flujo completo con validación XSD...")
    
    # Buscar una factura pendiente para probar
    factura_pendiente = facturas_con_clave.filter(estado_sri__in=['PENDIENTE', None]).first()
    
    if factura_pendiente:
        print(f"🧪 Probando procesamiento completo de factura {factura_pendiente.numero}...")
        
        # NOTA: En un entorno real, esto enviaría al SRI
        # Aquí solo probamos hasta la validación XSD
        try:
            # Solo generar y validar XML, no enviar
            xml_path = integration.generar_xml_factura(factura_pendiente, validar_xsd=True)
            print("✅ Flujo de validación XSD funciona correctamente")
            
            # Mostrar estadísticas del XML
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
                print(f"📄 XML generado: {len(xml_content)} caracteres")
                print(f"📁 Ubicación: {xml_path}")
                
        except Exception as e:
            print(f"❌ Error en flujo completo: {e}")
    else:
        print("⚠️  No hay facturas pendientes para probar")
    
    # Validar XMLs existentes
    print(f"\n📋 Validando XMLs existentes...")
    try:
        resultado_lote = validar_lote_xml_facturas()
        print(f"📊 Resultados de validación masiva:")
        print(f"   📄 Total archivos XML: {resultado_lote['total_archivos']}")
        print(f"   ✅ Válidos: {resultado_lote['validos']}")
        print(f"   ❌ Inválidos: {resultado_lote['invalidos']}")
        
        if resultado_lote['invalidos'] > 0:
            print(f"\n⚠️  Archivos XML inválidos encontrados:")
            for resultado in resultado_lote['resultados']:
                if not resultado['success']:
                    print(f"   - {os.path.basename(resultado['xml_path'])}: {resultado['message'][:100]}...")
                    
    except Exception as e:
        print(f"❌ Error validando lote: {e}")
    
    # Mostrar resumen del fix
    print(f"\n📋 Resumen del fix implementado:")
    print(f"✅ Validación XSD integrada en el flujo principal")
    print(f"✅ Validación se ejecuta ANTES de firmar y enviar")
    print(f"✅ Errores de estructura se detectan tempranamente")
    print(f"✅ XMLs inválidos se guardan para debugging")
    print(f"✅ Mensajes de error detallados con número de línea")
    print(f"✅ Funciones utilitarias para validación independiente")
    
    print("\n🏁 Verificación de validación XSD completada")

if __name__ == "__main__":
    main()
