"""
Integración Django para Guías de Remisión - SRI Ecuador
Completamente independiente de la integración de facturas
"""
import logging
import os
from datetime import datetime
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from inventario.models import GuiaRemision, Opciones
from .xml_generator_guia import XMLGeneratorGuiaRemision
from .firmador_guia import FirmadorGuiaRemision
from inventario.sri.sri_client import SRIClient

logger = logging.getLogger(__name__)


class IntegracionGuiaRemisionSRI:
    """
    Clase de integración para procesar Guías de Remisión con el SRI
    """
    
    def __init__(self, empresa):
        """
        Inicializa la integración con la empresa
        
        Args:
            empresa: Instancia del modelo Empresa
        """
        self.empresa = empresa
        self.opciones = Opciones.objects.filter(empresa=empresa).first()
        
        if not self.opciones:
            raise ValueError(f"No se encontraron opciones configuradas para la empresa {empresa.razon_social}")
    
    def procesar_guia_remision(self, guia_id):
        """
        Procesa una guía de remisión completa: genera XML, firma y envía al SRI
        
        Args:
            guia_id: ID de la guía de remisión
            
        Returns:
            dict: Resultado del procesamiento
        """
        try:
            # Obtener la guía
            guia = GuiaRemision.objects.get(id=guia_id, empresa=self.empresa)
            
            # 1. Generar clave de acceso si no existe
            if not guia.clave_acceso:
                generator = XMLGeneratorGuiaRemision(guia, self.empresa, self.opciones)
                guia.clave_acceso = generator.generar_clave_acceso()
                guia.save()
            
            # 2. Generar XML
            xml_sin_firmar = self.generar_xml(guia)
            
            # 3. Firmar XML
            xml_firmado = self.firmar_xml(xml_sin_firmar)
            
            # 4. Guardar XML firmado
            self._guardar_xml(guia, xml_firmado)
            
            # 5. Enviar al SRI
            resultado_envio = self.enviar_guia_sri(guia, xml_firmado)
            
            if resultado_envio.get('success'):
                # 6. Consultar autorización
                resultado_autorizacion = self.consultar_autorizacion(guia)
                
                if resultado_autorizacion.get('estado') == 'AUTORIZADO':
                    guia.estado = 'autorizada'
                    guia.numero_autorizacion = resultado_autorizacion.get('numero_autorizacion')
                    guia.fecha_autorizacion = datetime.now()
                    guia.save()
                    
                    return {
                        'success': True,
                        'message': 'Guía de remisión procesada y autorizada exitosamente',
                        'clave_acceso': guia.clave_acceso,
                        'numero_autorizacion': guia.numero_autorizacion
                    }
            
            return resultado_envio
            
        except GuiaRemision.DoesNotExist:
            logger.error(f"Guía de remisión {guia_id} no encontrada")
            return {
                'success': False,
                'message': f'Guía de remisión {guia_id} no encontrada'
            }
        except Exception as e:
            logger.error(f"Error procesando guía de remisión: {e}")
            return {
                'success': False,
                'message': f'Error procesando guía de remisión: {str(e)}'
            }
    
    def generar_xml(self, guia):
        """
        Genera el XML de la guía de remisión
        
        Args:
            guia: Instancia de GuiaRemision
            
        Returns:
            str: XML sin firmar
        """
        try:
            generator = XMLGeneratorGuiaRemision(guia, self.empresa, self.opciones)
            xml_string = generator.generar_xml()
            
            logger.info(f"XML generado para guía {guia.numero_completo}")
            return xml_string
            
        except Exception as e:
            logger.error(f"Error generando XML: {e}")
            raise
    
    def firmar_xml(self, xml_string):
        """
        Firma digitalmente el XML de la guía de remisión
        
        Args:
            xml_string (str): XML sin firmar
            
        Returns:
            str: XML firmado
        """
        try:
            # Obtener la ruta del archivo P12
            if not self.opciones.firma_electronica:
                raise ValueError("No hay firma electrónica configurada")
            
            archivo_p12 = self.opciones.firma_electronica.path
            password = self.opciones.clave_firma
            
            # Firmar
            firmador = FirmadorGuiaRemision(archivo_p12, password)
            xml_firmado = firmador.firmar_xml(xml_string)
            
            logger.info("XML de guía de remisión firmado exitosamente")
            return xml_firmado
            
        except Exception as e:
            logger.error(f"Error firmando XML: {e}")
            raise
    
    def enviar_guia_sri(self, guia, xml_firmado):
        """
        Envía la guía de remisión al SRI
        
        Args:
            guia: Instancia de GuiaRemision
            xml_firmado (str): XML firmado
            
        Returns:
            dict: Resultado del envío
        """
        try:
            # Crear cliente SRI
            ambiente = self.opciones.ambiente_sri
            cliente = SRIClient(ambiente=ambiente)
            
            # Enviar comprobante
            resultado = cliente.enviar_comprobante(xml_firmado)
            
            logger.info(f"Guía {guia.numero_completo} enviada al SRI")
            return resultado
            
        except Exception as e:
            logger.error(f"Error enviando guía al SRI: {e}")
            return {
                'success': False,
                'message': f'Error enviando al SRI: {str(e)}'
            }
    
    def consultar_autorizacion(self, guia):
        """
        Consulta el estado de autorización de la guía en el SRI
        
        Args:
            guia: Instancia de GuiaRemision
            
        Returns:
            dict: Estado de autorización
        """
        try:
            if not guia.clave_acceso:
                return {
                    'estado': 'ERROR',
                    'mensaje': 'La guía no tiene clave de acceso'
                }
            
            # Crear cliente SRI
            ambiente = self.opciones.ambiente_sri
            cliente = SRIClient(ambiente=ambiente)
            
            # Consultar autorización
            resultado = cliente.consultar_autorizacion(guia.clave_acceso)
            
            logger.info(f"Autorización consultada para guía {guia.numero_completo}")
            return resultado
            
        except Exception as e:
            logger.error(f"Error consultando autorización: {e}")
            return {
                'estado': 'ERROR',
                'mensaje': f'Error consultando autorización: {str(e)}'
            }
    
    def _guardar_xml(self, guia, xml_content):
        """
        Guarda el XML firmado en el storage
        
        Args:
            guia: Instancia de GuiaRemision
            xml_content (str): Contenido del XML
        """
        try:
            # Crear directorio si no existe
            directorio = f'guias_remision/{self.empresa.id}/'
            nombre_archivo = f'guia_{guia.numero_completo.replace("-", "_")}.xml'
            ruta_completa = os.path.join(directorio, nombre_archivo)
            
            # Guardar archivo
            content_file = ContentFile(xml_content.encode('utf-8'))
            ruta_guardada = default_storage.save(ruta_completa, content_file)
            
            # Actualizar guía con ruta del XML
            guia.xml_autorizado = xml_content
            guia.save()
            
            logger.info(f"XML guardado en: {ruta_guardada}")
            
        except Exception as e:
            logger.error(f"Error guardando XML: {e}")
            # No lanzamos excepción para no detener el proceso


def procesar_guia_async(guia_id, empresa_id):
    """
    Función auxiliar para procesar guías de forma asíncrona
    Puede ser usada con Celery o similar
    
    Args:
        guia_id: ID de la guía
        empresa_id: ID de la empresa
    """
    try:
        from inventario.models import Empresa
        
        empresa = Empresa.objects.get(id=empresa_id)
        integracion = IntegracionGuiaRemisionSRI(empresa)
        resultado = integracion.procesar_guia_remision(guia_id)
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error en procesamiento asíncrono: {e}")
        return {
            'success': False,
            'message': str(e)
        }
