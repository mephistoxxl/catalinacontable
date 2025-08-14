#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar la configuración de firma electrónica
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Opciones
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verificar_configuracion_firma():
    """Verifica la configuración de firma electrónica"""
    
    print("=== VERIFICACIÓN DE CONFIGURACIÓN DE FIRMA ELECTRÓNICA ===")
    
    try:
        # Obtener configuración
        opciones = Opciones.objects.first()
        
        if not opciones:
            print("❌ No se encontró ninguna configuración en Opciones")
            return False
            
        print(f"✅ Configuración encontrada (ID: {opciones.id})")
        
        # Verificar firma electrónica
        if not opciones.firma_electronica:
            print("❌ No hay archivo de firma electrónica configurado")
            print("   - Ve a Configuración > Opciones y sube tu archivo .p12 o .pfx")
            return False
            
        print(f"✅ Archivo de firma configurado: {opciones.firma_electronica.name}")
        
        # Verificar que el archivo existe
        firma_path = opciones.firma_electronica.path
        if not os.path.exists(firma_path):
            print(f"❌ El archivo de firma no existe en: {firma_path}")
            return False
            
        print(f"✅ Archivo de firma existe: {firma_path}")
        
        # Verificar contraseña
        if not opciones.password_firma:
            print("❌ No hay contraseña configurada")
            print("   - Ve a Configuración > Opciones y establece la contraseña")
            return False
            
        print("✅ Contraseña de firma configurada")
        
        # Verificar fecha de caducidad
        if not opciones.fecha_caducidad_firma:
            print("⚠️  Fecha de caducidad no establecida")
            print("   - La fecha se extraerá automáticamente cuando guardes la configuración")
        else:
            print(f"✅ Fecha de caducidad: {opciones.fecha_caducidad_firma}")
            
            # Verificar si está vencido
            from datetime import date
            if opciones.fecha_caducidad_firma < date.today():
                print("❌ ¡El certificado está vencido!")
                return False
            else:
                print("✅ Certificado vigente")
        
        # Verificar que podemos leer el certificado
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12
            from cryptography.hazmat.backends import default_backend
            
            with open(firma_path, 'rb') as f:
                p12_data = f.read()
            
            password = opciones.password_firma.encode()
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                p12_data, password, backend=default_backend()
            )
            
            if certificate:
                print("✅ Certificado leído exitosamente")
                print(f"   - Sujeto: {certificate.subject}")
                print(f"   - Emisor: {certificate.issuer}")
                print(f"   - Válido hasta: {certificate.not_valid_after}")
            else:
                print("❌ No se encontró certificado en el archivo")
                return False
                
        except Exception as e:
            print(f"❌ Error al leer el certificado: {e}")
            print("   - Verifica que la contraseña sea correcta")
            print("   - Verifica que el archivo .p12 sea válido")
            return False
            
        print("\n🎉 ¡Configuración de firma electrónica verificada exitosamente!")
        return True
        
    except Exception as e:
        print(f"❌ Error al verificar configuración: {e}")
        return False

if __name__ == "__main__":
    verificar_configuracion_firma()