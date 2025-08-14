#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para configurar y verificar la firma electrónica de RIDE PDF
Este script asegura que el RIDE salga firmado correctamente con Python 3.13+
"""

import os
import sys
import logging
from pathlib import Path

# Agregar el directorio actual al path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verificar_firma_electronica():
    """Verifica la configuración de firma electrónica"""
    print("🔍 Verificando configuración de firma electrónica...")
    
    try:
        from inventario.models import Opciones
        
        # Verificar si existe configuración
        opciones = Opciones.objects.first()
        if not opciones:
            print("❌ No se encontró configuración de Opciones")
            return False
            
        # Verificar archivo de firma
        if not opciones.firma_electronica:
            print("❌ No se ha configurado archivo de firma electrónica")
            print("   Ve a Admin > Opciones > Firma Electrónica y sube tu archivo .p12")
            return False
            
        if not opciones.password_firma:
            print("❌ No se ha configurado contraseña de firma electrónica")
            return False
            
        print("✅ Archivo de firma electrónica configurado")
        print(f"   Archivo: {opciones.firma_electronica.name}")
        print(f"   Caducidad: {opciones.fecha_caducidad_firma}")
        
        # Verificar que el archivo existe
        if not os.path.exists(opciones.firma_electronica.path):
            print("❌ El archivo de firma no existe en el sistema de archivos")
            return False
            
        print("✅ Archivo de firma existe en el sistema")
        
        # Verificar que podemos leer el certificado
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12
            from cryptography.hazmat.backends import default_backend
            
            with opciones.firma_electronica.open('rb') as f:
                p12_data = f.read()
            
            password = opciones.password_firma.encode()
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                p12_data, password, backend=default_backend()
            )
            
            if certificate:
                print("✅ Certificado válido y leído exitosamente")
                print(f"   Emisor: {certificate.issuer}")
                print(f"   Sujeto: {certificate.subject}")
                print(f"   Válido hasta: {certificate.not_valid_after}")
                return True
            else:
                print("❌ No se pudo leer el certificado")
                return False
                
        except Exception as e:
            print(f"❌ Error leyendo certificado: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando configuración: {e}")
        return False

def verificar_pdf_firmador():
    """Verifica que el sistema de PDF signing funcione"""
    print("\n🔍 Verificando sistema de PDF signing...")
    
    try:
        from inventario.sri.pdf_firmador import PDFFirmador
        
        # Intentar crear una instancia
        firmador = PDFFirmador()
        print("✅ PDFFirmador inicializado correctamente")
        
        # Verificar que puede cargar configuración
        if firmador.opciones:
            print("✅ Configuración cargada correctamente")
            return True
        else:
            print("❌ No se pudo cargar la configuración")
            return False
            
    except Exception as e:
        print(f"❌ Error con PDFFirmador: {e}")
        return False

def verificar_compatibilidad_python313():
    """Verifica compatibilidad con Python 3.13+"""
    print("\n🔍 Verificando compatibilidad Python 3.13+...")
    
    version = sys.version_info
    print(f"   Python versión: {version.major}.{version.minor}.{version.micro}")
    
    # Verificar legacy-cgi
    try:
        import legacy_cgi as cgi
        print("✅ legacy-cgi disponible")
    except ImportError:
        print("❌ legacy-cgi no instalado")
        print("   Ejecuta: python -m pip install legacy-cgi")
        return False
    
    # Verificar Django
    try:
        import django
        print(f"✅ Django {django.get_version()} disponible")
    except ImportError:
        print("❌ Django no disponible")
        return False
    
    return True

def pasos_para_firma_activa():
    """Muestra los pasos para activar la firma electrónica"""
    print("\n📋 PASOS PARA ACTIVAR FIRMA ELECTRÓNICA:")
    print("1. Obtén tu certificado digital (.p12) del SRI o autoridad certificadora")
    print("2. Accede al panel de administración Django")
    print("3. Ve a: Opciones > [Tu empresa] > Firma Electrónica")
    print("4. Sube tu archivo .p12")
    print("5. Ingresa la contraseña del certificado")
    print("6. Guarda los cambios")
    print("7. La fecha de caducidad se extraerá automáticamente")
    print("8. Las nuevas facturas generarán RIDE firmado automáticamente")

def main():
    """Función principal"""
    print("🚀 Configuración de Firma Electrónica - RIDE PDF Firmado")
    print("=" * 60)
    
    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
    
    try:
        import django
        django.setup()
    except Exception as e:
        print(f"❌ Error configurando Django: {e}")
        return
    
    # Verificaciones
    compat_ok = verificar_compatibilidad_python313()
    firma_ok = verificar_firma_electronica()
    pdf_ok = verificar_pdf_firmador()
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE CONFIGURACIÓN:")
    print(f"   Compatibilidad Python 3.13+: {'✅' if compat_ok else '❌'}")
    print(f"   Firma Electrónica Configurada: {'✅' if firma_ok else '❌'}")
    print(f"   Sistema PDF Signing: {'✅' if pdf_ok else '❌'}")
    
    if all([compat_ok, firma_ok, pdf_ok]):
        print("\n🎉 ¡TODO LISTO! Las nuevas facturas generarán RIDE firmado")
        print("   Genera una nueva factura y descarga el RIDE - vendrá firmado")
    else:
        print("\n⚠️ FALTAN PASOS:")
        if not compat_ok:
            print("   - Instala las dependencias faltantes")
        if not firma_ok:
            print("   - Configura la firma electrónica siguiendo los pasos arriba")
        if not pdf_ok:
            print("   - Verifica el sistema de PDF signing")
        
        pasos_para_firma_activa()

if __name__ == "__main__":
    main()