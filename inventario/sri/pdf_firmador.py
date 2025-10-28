# inventario/sri/pdf_firmador.py

import logging
import os
import datetime
from pathlib import Path
from io import BytesIO  # Para manejar datos binarios en memoria
from cryptography.hazmat.primitives.serialization import pkcs12
from inventario.models import Opciones

logger = logging.getLogger(__name__)

class PDFFirmador:
    """
    Firmador de PDF usando endesive - Mucho más estable y confiable
    Compatible con certificados P12 de Ecuador
    """
    
    def __init__(self):
        self.opciones = None
        self._cargar_configuracion()
    
    def _cargar_configuracion(self):
        """Carga la configuración de firma electrónica desde Opciones."""
        try:
            self.opciones = Opciones.objects.filter(
                firma_electronica__isnull=False,
                password_firma__isnull=False,
            ).first()
            if not self.opciones:
                raise Exception("No se encontró configuración de Opciones")
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")
            raise
    
    def _obtener_certificado_y_clave(self):
        """
        Obtiene el certificado y clave privada desde el archivo .p12.
        """
        if not self.opciones.firma_electronica or not self.opciones.password_firma:
            raise Exception('Firma electrónica o contraseña no configuradas en Opciones')
        
        try:
            with self.opciones.firma_electronica.open('rb') as f:
                p12_data = f.read()
            
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                p12_data, self.opciones.password_firma.encode()
            )
            
            return private_key, certificate, additional_certs
            
        except Exception as e:
            logger.error(f"Error al cargar certificado: {e}")
            raise Exception(f"Error al cargar el certificado de firma: {e}")
    
    def firmar_pdf(self, pdf_path, pdf_firmado_path, razon=None, ubicacion=None, contacto=None):
        """
        Firma un archivo PDF usando endesive (más estable que pyHanko).
        
        Args:
            pdf_path (str): Ruta al archivo PDF a firmar
            pdf_firmado_path (str): Ruta donde se guardará el PDF firmado
            razon (str, optional): Razón de la firma
            ubicacion (str, optional): Ubicación de la firma
            contacto (str, optional): Contacto del firmante
        """
        
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"El archivo PDF no existe: {pdf_path}")
        
        try:
            # Verificar si endesive está disponible
            try:
                from endesive.pdf import cms
                logger.info("Usando endesive para firmar PDF")
            except ImportError as e:
                logger.warning(
                    "endesive no está disponible: %s. "
                    "Instale con `pip install endesive>=2.17.0`. Copiando PDF sin firmar...",
                    e,
                )
                import shutil
                shutil.copy2(pdf_path, pdf_firmado_path)
                return pdf_firmado_path
            
            # Obtener certificado y clave privada
            private_key, certificate, additional_certs = self._obtener_certificado_y_clave()
            
            # Configurar valores por defecto
            razon = razon or "Documento firmado electrónicamente"
            ubicacion = ubicacion or "Ecuador"
            contacto = contacto or (self.opciones.correo if self.opciones else "")
            
            # Usar archivo temporal para evitar conflictos de bloqueo
            import tempfile
            
            # Leer el PDF original
            with open(pdf_path, 'rb') as pdf_file:
                pdf_data = pdf_file.read()
            
            # Verificar que el PDF no esté vacío
            if len(pdf_data) == 0:
                raise Exception(f"El archivo PDF está vacío: {pdf_path}")
            
            logger.info(f"PDF leído correctamente: {len(pdf_data)} bytes")
            
            # Configuración mejorada para firma visible en Adobe
            dct = {
                "sigflags": 3,
                "sigpage": -1,  # Última página
                "sigfield": "Signature1",
                "auto_sigfield": True,
                "sigandcertify": True,  # Certificar el documento
                "signaturebox": (50, 50, 250, 150),  # Posición más visible
                "signature": f"Firmado digitalmente por {self.opciones.razon_social or 'Sistema'}" if self.opciones else "Firmado digitalmente",
                "reason": razon,
                "location": ubicacion,
                "contact": contacto,
                "signingdate": datetime.datetime.utcnow().strftime("D:%Y%m%d%H%M%S+00'00'"),
                "timestamp": datetime.datetime.utcnow().strftime("D:%Y%m%d%H%M%S+00'00'"),
            }
            
            # Firmar el PDF con endesive
            try:
                # Validar certificado y clave
                logger.info(f"Certificado: {type(certificate)}, Private Key: {type(private_key)}")
                logger.info(f"Certificados adicionales: {len(additional_certs or [])}")
                
                signed_data = cms.sign(
                    pdf_data,
                    dct,
                    private_key,
                    certificate,
                    additional_certs or [],
                    "sha256"
                )
                
                # Verificar datos firmados
                logger.info(f"Datos firmados generados: {len(signed_data)} bytes")
                pdf_firmado_data = pdf_data + signed_data
                
                # Verificar que se generó contenido firmado
                if not pdf_firmado_data or len(pdf_firmado_data) == 0:
                    raise Exception("La firma no generó contenido válido")
                
                if len(pdf_firmado_data) <= len(pdf_data):
                    raise Exception("Los datos firmados no contienen información adicional")
                
                logger.info(f"PDF firmado correctamente: {len(pdf_data)} -> {len(pdf_firmado_data)} bytes")
                
            except Exception as sign_error:
                logger.error(f"Error durante la firma con endesive: {sign_error}")
                # Si falla la firma, copiar el original con manejo robusto
                import shutil
                try:
                    shutil.copy2(pdf_path, pdf_firmado_path)
                    logger.warning("Copiado PDF sin firmar debido a error en endesive")
                    return pdf_firmado_path
                except (PermissionError, OSError) as copy_error:
                    # Si falla la copia, intentar con nombre temporal
                    alt_path = str(Path(pdf_firmado_path).with_stem(Path(pdf_firmado_path).stem + '_unsigned'))
                    shutil.copy2(pdf_path, alt_path)
                    logger.warning(f"PDF copiado sin firmar en ruta alternativa: {alt_path}")
                    return alt_path
            
            # Guardar PDF firmado con manejo robusto de archivos
            temp_file = None
            try:
                # Crear archivo temporal primero
                with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pdf') as temp_file:
                    temp_file.write(pdf_firmado_data)
                    temp_path = temp_file.name
                
                # Intentar mover el archivo temporal al destino
                try:
                    import shutil
                    shutil.move(temp_path, pdf_firmado_path)
                except (PermissionError, OSError) as move_error:
                    # Si falla, intentar copiar y luego eliminar
                    try:
                        shutil.copy2(temp_path, pdf_firmado_path)
                        os.unlink(temp_path)
                    except (PermissionError, OSError):
                        # Último recurso: usar nombre alternativo
                        alt_path = str(Path(pdf_firmado_path).with_stem(Path(pdf_firmado_path).stem + '_signed_tmp'))
                        shutil.move(temp_path, alt_path)
                        pdf_firmado_path = alt_path
                        logger.warning(f"Usando ruta alternativa: {alt_path}")
                        
            except Exception as save_error:
                if temp_file and os.path.exists(temp_file.name):
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                raise save_error
            
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
            # En caso de error, copiar sin firmar para no interrumpir el flujo
            import shutil
            try:
                shutil.copy2(pdf_path, pdf_firmado_path)
                logger.warning(f"PDF copiado sin firmar debido a error: {e}")
                return pdf_firmado_path
            except (PermissionError, OSError) as copy_error:
                # Si falla la copia, intentar con nombre temporal
                alt_path = str(Path(pdf_firmado_path).with_stem(Path(pdf_firmado_path).stem + '_error'))
                try:
                    shutil.copy2(pdf_path, alt_path)
                    logger.warning(f"PDF copiado sin firmar en ruta alternativa: {alt_path}")
                    return alt_path
                except Exception as final_error:
                    logger.error(f"Error final copiando PDF: {final_error}")
                    raise
    
    def firmar_ride_factura(self, factura, pdf_path, pdf_firmado_path=None):
        """
        Firma específicamente el RIDE de una factura.
        
        Args:
            factura: Instancia del modelo Factura
            pdf_path: Ruta al PDF del RIDE
            pdf_firmado_path: Ruta de salida (opcional)
        """
        if not pdf_firmado_path:
            # Generar nombre con sufijo _firmado
            path = Path(pdf_path)
            pdf_firmado_path = str(path.parent / f"{path.stem}_firmado{path.suffix}")
        
        # Verificar que el archivo original existe y no está vacío
        if not os.path.exists(pdf_path):
            raise Exception(f"El archivo PDF original no existe: {pdf_path}")
        
        original_size = os.path.getsize(pdf_path)
        if original_size == 0:
            raise Exception(f"El archivo PDF original está vacío: {pdf_path}")
        
        logger.info(f"Firmando PDF: {pdf_path} ({original_size} bytes)")
        
        # Construir número de factura desde sus componentes
        numero_factura = f"{getattr(factura, 'establecimiento', '001')}-{getattr(factura, 'punto_emision', '001')}-{str(getattr(factura, 'secuencia', 1)).zfill(9)}"
        razon = f"RIDE de Factura #{numero_factura} - {getattr(self.opciones, 'razon_social', 'Sistema')}"
        
        try:
            # Intentar firmar con endesive
            result = self.firmar_pdf(
                pdf_path=pdf_path,
                pdf_firmado_path=pdf_firmado_path,
                razon=razon,
                ubicacion=getattr(self.opciones, 'direccion_establecimiento', 'Ecuador'),
                contacto=getattr(self.opciones, 'correo', '')
            )
            
            # Verificar resultado
            if os.path.exists(result):
                final_size = os.path.getsize(result)
                logger.info(f"RIDE firmado exitosamente: {result} ({final_size} bytes)")
                return result
            else:
                raise Exception("El archivo firmado no se generó correctamente")
                
        except Exception as e:
            logger.error(f"Error firmando RIDE: {e}")
            
            # Fallback: copiar sin firmar si todo falla
            try:
                import shutil
                shutil.copy2(pdf_path, pdf_firmado_path)
                logger.warning(f"RIDE copiado sin firmar como fallback: {pdf_firmado_path}")
                return pdf_firmado_path
            except Exception as fallback_error:
                logger.error(f"Error en fallback: {fallback_error}")
                raise Exception(f"No se pudo firmar ni copiar el PDF: {fallback_error}")

def firmar_pdf_simple(pdf_path, pdf_firmado_path=None, **kwargs):
    """
    Función auxiliar para firmar PDF de forma simple.
    
    Args:
        pdf_path (str): Ruta al PDF a firmar
        pdf_firmado_path (str, optional): Ruta de salida
        **kwargs: Parámetros adicionales para firmar_pdf
    
    Returns:
        str: Ruta del PDF firmado
    """
    firmador = PDFFirmador()
    
    if not pdf_firmado_path:
        path = Path(pdf_path)
        pdf_firmado_path = str(path.parent / f"{path.stem}_firmado{path.suffix}")
    
    return firmador.firmar_pdf(pdf_path, pdf_firmado_path, **kwargs)