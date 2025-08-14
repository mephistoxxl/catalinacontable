#!/usr/bin/env python3
"""
Firmador de PDF completamente independiente de Django
"""
import os
import sys
import logging
from pathlib import Path
from cryptography.hazmat.primitives.serialization import pkcs12

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StandalonePDFFirmador:
    """
    Firmador de PDF sin dependencias Django
    """
    
    def __init__(self, cert_path, cert_password):
        self.cert_path = cert_path
        self.cert_password = cert_password
        
    def _obtener_certificado_y_clave(self):
        """Obtiene el certificado y clave privada desde el archivo .p12."""
        
        if not os.path.exists(self.cert_path):
            raise Exception(f'Certificado no encontrado: {self.cert_path}')
        
        try:
            with open(self.cert_path, 'rb') as f:
                p12_data = f.read()
            
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                p12_data, self.cert_password.encode()
            )
            
            return private_key, certificate, additional_certs
            
        except Exception as e:
            logger.error(f"Error al cargar certificado: {e}")
            raise Exception(f"Error al cargar el certificado de firma: {e}")
    
    def firmar_pdf(self, pdf_path, pdf_firmado_path, razon=None, ubicacion=None, contacto=None):
        """Firma un archivo PDF usando endesive."""
        
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"El archivo PDF no existe: {pdf_path}")
        
        try:
            # Verificar si endesive está disponible
            try:
                from endesive.pdf import cms
                logger.info("Usando endesive para firmar PDF")
            except ImportError as e:
                logger.error(f"endesive no está disponible: {e}")
                raise
            
            # Obtener certificado y clave privada
            private_key, certificate, additional_certs = self._obtener_certificado_y_clave()
            
            # Configurar valores por defecto
            razon = razon or "Documento firmado electrónicamente"
            ubicacion = ubicacion or "Ecuador"
            contacto = contacto or "test@example.com"
            
            # Leer el PDF original
            with open(pdf_path, 'rb') as pdf_file:
                pdf_data = pdf_file.read()
            
            # Verificar que el PDF no esté vacío
            if len(pdf_data) == 0:
                raise Exception(f"El archivo PDF está vacío: {pdf_path}")
            
            logger.info(f"PDF leído correctamente: {len(pdf_data)} bytes")
            
            # Configuración para endesive
            dct = {
                "sigflags": 3,
                "sigpage": 0,
                "sigfield": "Signature1",
                "auto_sigfield": True,
                "sigandcertify": False,
                "signaturebox": (450, 50, 580, 100),
                "signature": f"Firmado digitalmente",
                "reason": razon,
                "location": ubicacion,
                "contact": contacto,
            }
            
            # Firmar el PDF
            signed_data = cms.sign(
                pdf_data,
                dct,
                private_key,
                certificate,
                additional_certs or [],
                "sha256"
            )
            
            # Concatenar PDF original + datos firmados (método estándar)
            pdf_firmado_data = pdf_data + signed_data
            
            # Verificar que se generó contenido firmado
            if not pdf_firmado_data or len(pdf_firmado_data) == 0:
                raise Exception("La firma no generó contenido válido")
            
            logger.info(f"PDF firmado correctamente: {len(pdf_firmado_data)} bytes")
            
            # Guardar PDF firmado
            with open(pdf_firmado_path, 'wb') as f:
                f.write(pdf_firmado_data)
            
            # Verificar que el archivo se guardó correctamente
            if not os.path.exists(pdf_firmado_path):
                raise Exception(f"No se pudo crear el archivo firmado: {pdf_firmado_path}")
            
            file_size = os.path.getsize(pdf_firmado_path)
            if file_size == 0:
                raise Exception("El archivo firmado está vacío")
            
            logger.info(f"PDF firmado exitosamente: {pdf_firmado_path} ({file_size} bytes)")
            return pdf_firmado_path
            
        except Exception as e:
            logger.error(f"Error al firmar PDF: {e}")
            raise

def main():
    print("🔍 Prueba de Firma de PDF (Completamente Standalone)")
    print("=" * 50)
    
    # Ruta al PDF de prueba
    pdf_original = 'media/facturas_pdf/RIDE_004-005-000000002.pdf'
    pdf_firmado = 'media/test_signed_final.pdf'
    
    # Buscar certificado .p12 en media/firmas/
    cert_dir = Path('media/firmas')
    cert_files = list(cert_dir.glob('*.p12'))
    
    if not cert_files:
        print("❌ No se encontró ningún certificado .p12 en media/firmas/")
        print("   Por favor, coloca tu certificado .p12 en la carpeta media/firmas/")
        return
    
    cert_path = cert_files[0]  # Usar el primer certificado encontrado
    print(f"📋 Certificado encontrado: {cert_path.name}")
    
    # Contraseña del certificado (puedes cambiarla o pedirla)
    cert_password = "123456"  # Contraseña por defecto para pruebas
    
    if not os.path.exists(pdf_original):
        print(f"❌ PDF original no encontrado: {pdf_original}")
        return
    
    try:
        firmador = StandalonePDFFirmador(
            cert_path=str(cert_path),
            cert_password=cert_password
        )
        
        result = firmador.firmar_pdf(
            pdf_path=pdf_original,
            pdf_firmado_path=pdf_firmado,
            razon="Prueba de firma electrónica",
            ubicacion="Ecuador",
            contacto="test@example.com"
        )
        
        if os.path.exists(result):
            size = os.path.getsize(result)
            print(f"✅ PDF firmado generado exitosamente!")
            print(f"   📁 Archivo: {result}")
            print(f"   📊 Tamaño: {size:,} bytes")
            
            # Verificación básica
            with open(result, 'rb') as f:
                content = f.read(4)
                if content == b'%PDF':
                    print("✅ El PDF inicia correctamente (%PDF)")
                else:
                    print("❌ El PDF no inicia con %PDF - Posible corrupción")
            
            print("\n💡 Prueba completada exitosamente!")
            print("   - Abre el PDF con Adobe Reader")
            print("   - Busca el sello de firma digital")
            print("   - Verifica que se abre sin errores")
        else:
            print("❌ No se generó el PDF firmado")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()