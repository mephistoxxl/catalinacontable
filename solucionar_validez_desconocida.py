#!/usr/bin/env python3
"""
Script para diagnosticar y solucionar el problema de "validez desconocida" en firmas PDF.
Este script verifica:
1. Configuración del certificado
2. Cadena de certificación
3. Validez del certificado
4. Proporciona instrucciones para agregar el certificado a confianza
"""

import os
import sys
import logging
from pathlib import Path
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
import django
django.setup()

from inventario.models import Opciones

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VerificadorValidez:
    """
    Verifica la configuración del certificado y proporciona soluciones
    para el problema de "validez desconocida".
    """
    
    def __init__(self):
        self.opciones = None
        self._cargar_configuracion()
    
    def _cargar_configuracion(self):
        """Carga la configuración de firma electrónica."""
        try:
            self.opciones = Opciones.objects.first()
            if not self.opciones:
                raise Exception("No se encontró configuración de Opciones")
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")
            raise
    
    def verificar_certificado(self):
        """
        Verifica el certificado y proporciona información detallada.
        """
        print("=== VERIFICACIÓN DE CERTIFICADO ===\n")
        
        if not self.opciones.firma_electronica:
            print("❌ No hay certificado configurado")
            return False
        
        if not self.opciones.password_firma:
            print("❌ No hay contraseña configurada")
            return False
        
        try:
            # Cargar el certificado
            with open(self.opciones.firma_electronica.path, 'rb') as f:
                p12_data = f.read()
            
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                p12_data, self.opciones.password_firma.encode(), backend=default_backend()
            )
            
            print(f"✅ Certificado cargado exitosamente")
            print(f"📄 Número de certificados adicionales: {len(additional_certs or [])}")
            
            # Información del certificado
            subject = certificate.subject
            issuer = certificate.issuer
            
            print(f"\n📋 INFORMACIÓN DEL CERTIFICADO:")
            print(f"   Emisor: {issuer.rfc4514_string()}")
            print(f"   Sujeto: {subject.rfc4514_string()}")
            print(f"   Fecha de inicio: {certificate.not_valid_before}")
            print(f"   Fecha de fin: {certificate.not_valid_after}")
            print(f"   Versión: {certificate.version}")
            print(f"   Serial: {certificate.serial_number}")
            
            # Verificar validez
            from datetime import datetime
            now = datetime.now()
            if certificate.not_valid_before <= now <= certificate.not_valid_after:
                print(f"   ✅ Certificado válido (dentro del período)")
            else:
                print(f"   ❌ Certificado expirado o no válido aún")
            
            # Verificar cadena de confianza
            if additional_certs and len(additional_certs) > 0:
                print(f"\n🔗 CADENA DE CERTIFICACIÓN:")
                for i, cert in enumerate(additional_certs, 1):
                    print(f"   Certificado {i}: {cert.subject.rfc4514_string()}")
            else:
                print(f"\n⚠️  ADVERTENCIA: No se encontraron certificados de cadena")
                print(f"   Esto puede causar el error 'validez desconocida'")
            
            return True
            
        except Exception as e:
            print(f"❌ Error al verificar certificado: {e}")
            return False
    
    def generar_informe_solucion(self):
        """
        Genera un informe con las soluciones para el problema.
        """
        print("\n" + "="*60)
        print("SOLUCIÓN: 'La validez de la firma es DESCONOCIDA'")
        print("="*60)
        
        print("""
🔍 PROBLEMA:
Adobe Reader muestra "La validez de la firma es DESCONOCIDA" porque:
1. El certificado no está en la lista de confianza del sistema
2. Falta la cadena completa de certificación (certificados raíz/intermedios)
3. El certificado es autofirmado o de una CA no reconocida

✅ SOLUCIONES:

1. AGREGAR CERTIFICADO A CONFIANZA:
   - Abrir el PDF firmado en Adobe Reader
   - Hacer clic en la firma (si es visible)
   - Seleccionar "Ver firmas" o "Ver certificado"
   - Hacer clic en "Agregar a confianza" o "Confiar en este certificado"
   - Marcar "Usar este certificado como entidad de confianza raíz"

2. INSTALAR CERTIFICADOS DE CADENA:
   - Descargar los certificados de la entidad emisora (CA)
   - Instalarlos en el sistema:
     * Windows: certmgr.msc -> Certificados raíz confiables
     * Adobe: Edit -> Preferences -> Signatures -> Identities & Trusted Certificates

3. VERIFICAR CERTIFICADO:
   - Asegúrate de que el certificado no esté expirado
   - Verifica que incluya la cadena completa de certificación

4. PARA USUARIOS FINALES:
   - Cada usuario debe agregar el certificado a su lista de confianza
   - O el administrador puede instalarlo globalmente en el sistema

📋 PASOS RECOMENDADOS:
""")
        
        # Generar instrucciones específicas
        if self.opciones and self.opciones.razon_social:
            print(f"   - Tu empresa: {self.opciones.razon_social}")
            print(f"   - Contacta a tu proveedor de certificados para obtener:")
            print(f"     * Certificado raíz de la CA")
            print(f"     * Certificados intermedios")
            print(f"     * Instrucciones de instalación")
        
        print("""
5. PARA PRUEBAS:
   - Puedes probar con un certificado de Let's Encrypt o similar
   - Los certificados de prueba mostrarán el mismo mensaje
   - Los certificados de producción deben ser de una CA reconocida

⚠️ NOTA IMPORTANTE:
Este mensaje es NORMAL para certificados de desarrollo o pruebas.
En producción, debes usar certificados de una Autoridad Certificadora reconocida.
""")
    
    def crear_certificado_pem(self):
        """
        Crea archivos PEM para facilitar la instalación manual.
        """
        if not (self.opciones.firma_electronica and self.opciones.password_firma):
            print("❌ No hay certificado configurado")
            return
        
        try:
            with open(self.opciones.firma_electronica.path, 'rb') as f:
                p12_data = f.read()
            
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                p12_data, self.opciones.password_firma.encode(), backend=default_backend()
            )
            
            # Guardar certificado en formato PEM
            cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
            
            output_path = Path("media/certificados/certificado_publico.pem")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(cert_pem)
            
            print(f"✅ Certificado público exportado a: {output_path}")
            print(f"   Puedes compartir este archivo para instalar en otros sistemas")
            
        except Exception as e:
            print(f"❌ Error al exportar certificado: {e}")

def main():
    """
    Ejecuta la verificación completa.
    """
    print("🔍 DIAGNÓSTICO DE VALIDEZ DE FIRMA PDF")
    print("="*50)
    
    try:
        verificador = VerificadorValidez()
        
        # Verificar certificado
        cert_ok = verificador.verificar_certificado()
        
        # Generar informe de solución
        verificador.generar_informe_solucion()
        
        # Exportar certificado PEM
        if cert_ok:
            verificador.crear_certificado_pem()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("   Asegúrate de tener Django configurado correctamente")

if __name__ == "__main__":
    main()