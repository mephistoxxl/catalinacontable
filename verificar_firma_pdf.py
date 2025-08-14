#!/usr/bin/env python3
"""
Script para verificar si un RIDE PDF está firmado electrónicamente
Este script te ayudará a confirmar que tu PDF tiene firma electrónica válida
"""

import os
import sys
import logging
from pathlib import Path

# Agregar el proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
import django
django.setup()

from inventario.models import Factura
from inventario.sri.ride_generator import RIDEGenerator
from inventario.sri.pdf_firmador import PDFFirmador

def verificar_firma_en_pdf(pdf_path):
    """
    Verifica si un PDF tiene firma electrónica
    """
    try:
        from pyhanko.sign.validation import validate_pdf_signature
        from pyhanko.pdf_utils.reader import PdfFileReader
        
        with open(pdf_path, 'rb') as doc:
            r = PdfFileReader(doc)
            
            # Obtener todos los campos de firma
            sig_fields = r.get_signature_fields()
            
            if not sig_fields:
                print("❌ El PDF NO tiene firma electrónica")
                return False
            
            print(f"✅ El PDF tiene {len(sig_fields)} campo(s) de firma")
            
            for field_name, sig_obj in sig_fields.items():
                print(f"\n📋 Campo de firma: {field_name}")
                
                # Validar la firma
                try:
                    status = validate_pdf_signature(sig_obj)
                    
                    if status.valid:
                        print("✅ La firma es VÁLIDA")
                        print(f"   Firmado por: {status.signer_name}")
                        print(f"   Fecha de firma: {status.signing_time}")
                        print(f"   Estado: {status.summary}")
                        return True
                    else:
                        print("❌ La firma es INVÁLIDA")
                        print(f"   Razón: {status.summary}")
                        
                except Exception as e:
                    print(f"❌ Error al validar firma: {e}")
            
            return True
            
    except ImportError:
        print("⚠️  pyhanko no está instalado. Usando método alternativo...")
        return verificar_firma_basica(pdf_path)
    except Exception as e:
        print(f"❌ Error al verificar firma: {e}")
        return False

def verificar_firma_basica(pdf_path):
    """
    Método básico para verificar presencia de firma
    """
    try:
        with open(pdf_path, 'rb') as f:
            content = f.read()
            
        # Buscar indicadores de firma electrónica
        firma_indicators = [
            b'/Sig',
            b'/Signature',
            b'/AcroForm',
            b'/SigFlags'
        ]
        
        firmado = any(indicator in content for indicator in firma_indicators)
        
        if firmado:
            print("✅ Se detectaron elementos de firma electrónica en el PDF")
            return True
        else:
            print("❌ No se detectaron elementos de firma electrónica")
            return False
            
    except Exception as e:
        print(f"❌ Error en verificación básica: {e}")
        return False

def listar_facturas_con_firma():
    """
    Lista las facturas y muestra si tienen PDF firmado
    """
    print("\n📊 Verificando facturas existentes...")
    
    facturas = Factura.objects.all().order_by('-id')[:10]
    
    if not facturas:
        print("❌ No hay facturas en el sistema")
        return
    
    for factura in facturas:
        print(f"\n📄 Factura #{factura.id}")
        print(f"   Cliente: {factura.nombre_cliente}")
        print(f"   Número: {factura.establecimiento}-{factura.punto_emision}-{factura.secuencia}")
        print(f"   Fecha: {factura.fecha_emision}")
        
        # Buscar PDF firmado
        ride_dir = os.path.join('media', 'ride')
        filename_firmado = f"RIDE_{factura.establecimiento}-{factura.punto_emision}-{factura.secuencia.zfill(9)}_firmado.pdf"
        filename_normal = f"RIDE_{factura.establecimiento}-{factura.punto_emision}-{factura.secuencia.zfill(9)}.pdf"
        
        pdf_firmado_path = os.path.join(ride_dir, filename_firmado)
        pdf_normal_path = os.path.join(ride_dir, filename_normal)
        
        if os.path.exists(pdf_firmado_path):
            print(f"   ✅ PDF FIRMADO: {filename_firmado}")
            verificar_firma_en_pdf(pdf_firmado_path)
        elif os.path.exists(pdf_normal_path):
            print(f"   ⚠️  PDF sin firmar: {filename_normal}")
            verificar_firma_en_pdf(pdf_normal_path)
        else:
            print("   ❌ PDF no encontrado")

def generar_y_verificar_ultima_factura():
    """
    Genera y verifica la firma de la última factura
    """
    print("\n🔄 Generando y verificando firma de última factura...")
    
    try:
        factura = Factura.objects.latest('id')
        print(f"Procesando factura #{factura.id}")
        
        # Generar RIDE firmado
        generator = RIDEGenerator()
        result = generator.generar_ride_factura_firmado(factura)
        
        if isinstance(result, tuple):
            pdf_normal, pdf_firmado = result
            print(f"✅ PDF generado y firmado:")
            print(f"   Normal: {pdf_normal}")
            print(f"   Firmado: {pdf_firmado}")
            
            # Verificar la firma
            verificar_firma_en_pdf(pdf_firmado)
        else:
            print(f"⚠️  PDF generado sin firma: {result}")
            verificar_firma_en_pdf(result)
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """
    Función principal del script
    """
    print("🔍 VERIFICADOR DE FIRMA ELECTRÓNICA EN RIDE PDF")
    print("=" * 50)
    
    while True:
        print("\nOpciones:")
        print("1. Verificar facturas existentes")
        print("2. Generar y verificar última factura")
        print("3. Verificar archivo PDF específico")
        print("4. Salir")
        
        opcion = input("\nSeleccione una opción (1-4): ").strip()
        
        if opcion == '1':
            listar_facturas_con_firma()
        elif opcion == '2':
            generar_y_verificar_ultima_factura()
        elif opcion == '3':
            pdf_path = input("Ingrese la ruta del PDF: ").strip()
            if os.path.exists(pdf_path):
                verificar_firma_en_pdf(pdf_path)
            else:
                print("❌ Archivo no encontrado")
        elif opcion == '4':
            break
        else:
            print("❌ Opción inválida")

if __name__ == "__main__":
    main()