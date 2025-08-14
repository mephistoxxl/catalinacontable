import os
import logging
import random
from datetime import datetime
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from inventario.models import Factura, DetalleFactura, Opciones
from .sri_client import SRIClient
from .xml_generator import SRIXMLGenerator
from .pdf_firmador import PDFFirmador

logger = logging.getLogger(__name__)

class SRIIntegration:
    """
    Clase de integración para conectar Django con el SRI
    """
    
    def __init__(self):
        """Inicializa la integración con configuración desde Django"""
        self.ambiente = getattr(settings, 'SRI_AMBIENTE', 'pruebas')
        self.cliente = SRIClient(ambiente=self.ambiente)
        
    def procesar_factura(self, factura_id):
        """
        Procesa una factura completa: genera XML, firma, envía al SRI y actualiza estado
        
        Args:
            factura_id (int): ID de la factura en la base de datos
            
        Returns:
            dict: Resultado del procesamiento
        """
        try:
            # Obtener factura
            factura = Factura.objects.get(id=factura_id)
            
            # Verificar que la factura esté en estado adecuado
            if factura.estado != 'PENDIENTE':
                return {
                    'success': False,
                    'message': f'La factura debe estar en estado PENDIENTE. Estado actual: {factura.estado}'
                }
            
            # Generar XML
            xml_generator = SRIXMLGenerator()
            xml_content = xml_generator.generar_xml_factura(factura)
            
            # Guardar XML temporalmente
            xml_filename = f"factura_{factura.numero}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
            xml_path = default_storage.path(f"facturas_xml/{xml_filename}")
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(xml_path), exist_ok=True)
            
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            # Firmar XML
            from .firmador import firmar_xml
            xml_firmado_path = xml_path.replace('.xml', '_firmado.xml')
            firmar_xml(xml_path, xml_firmado_path)
            
            # Generar clave de acceso
            clave_acceso = self._generar_clave_acceso(factura)
            
            # Enviar al SRI
            with open(xml_firmado_path, 'r', encoding='utf-8') as f:
                xml_firmado_content = f.read()
            
            resultado = self.cliente.enviar_comprobante(xml_firmado_content, clave_acceso)
            
            # Actualizar factura con resultado
            self._actualizar_factura_con_resultado(factura, resultado, clave_acceso)
            
            # Si fue recibido, solicitar autorización
            if resultado.get('estado') == 'RECIBIDA':
                resultado_auth = self.cliente.consultar_autorizacion(clave_acceso)
                
                if resultado_auth.get('estado') == 'AUTORIZADA':
                    # Generar RIDE autorizado
                    self._generar_ride_autorizado(factura, resultado_auth)
                    
                    return {
                        'success': True,
                        'message': 'Factura autorizada exitosamente',
                        'resultado': resultado_auth
                    }
                else:
                    return {
                        'success': False,
                        'message': f"Error en autorización: {resultado_auth.get('mensaje', 'Error desconocido')}",
                        'resultado': resultado_auth
                    }
            else:
                return {
                    'success': False,
                    'message': f"Error en recepción: {resultado.get('mensaje', 'Error desconocido')}",
                    'resultado': resultado
                }
                
        except Factura.DoesNotExist:
            return {
                'success': False,
                'message': f'No se encontró la factura con ID {factura_id}'
            }
        except Exception as e:
            logger.error(f"Error procesando factura {factura_id}: {str(e)}")
            return {
                'success': False,
                'message': f'Error interno: {str(e)}'
            }
    
    def generar_xml_factura(self, factura):
        """
        Genera el XML de una factura y lo guarda en el sistema de archivos
        
        Args:
            factura: Instancia de Factura
            
        Returns:
            str: Ruta del archivo XML generado
        """
        try:
            # Generar XML
            xml_generator = SRIXMLGenerator()
            xml_content = xml_generator.generar_xml_factura(factura)
            
            # Crear nombre de archivo único
            xml_filename = f"factura_{factura.numero}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
            xml_path = os.path.join(settings.MEDIA_ROOT, "facturas_xml", xml_filename)
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(xml_path), exist_ok=True)
            
            # Guardar XML
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            return xml_path
            
        except Exception as e:
            logger.error(f"Error generando XML para factura {factura.numero}: {str(e)}")
            raise Exception(f"Error generando XML: {str(e)}")
            
            # Obtener clave de acceso
            clave_acceso = self._generar_clave_acceso(factura)
            
            # Enviar al SRI
            resultado = self.cliente.procesar_comprobante_completo(
                xml_content, 
                clave_acceso,
                max_intentos=3,
                espera_segundos=3
            )
            
            # Actualizar factura con resultado
            self._actualizar_factura_con_resultado(factura, resultado, clave_acceso)
            
            # Si fue autorizado, generar RIDE
            if resultado['estado'] == 'AUTORIZADO':
                self._generar_ride_autorizado(factura, resultado)
            
            # Limpiar archivo temporal
            try:
                default_storage.delete(saved_xml_path)
            except:
                pass
            
            return {
                'success': True,
                'resultado': resultado,
                'clave_acceso': clave_acceso
            }
            
        except Factura.DoesNotExist:
            return {
                'success': False,
                'message': f'Factura con ID {factura_id} no encontrada'
            }
        except Exception as e:
            logger.error(f"Error procesando factura {factura_id}: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def _generar_clave_acceso(self, factura):
        """
        Genera la clave de acceso según especificaciones del SRI
        
        Args:
            factura: Instancia de Factura
            
        Returns:
            str: Clave de acceso generada
        """
        # Formato: [fecha(8)][tipo_comprobante(2)][ruc(13)][ambiente(1)][serie(6)][numero_secuencial(9)][codigo_numerico(8)][tipo_emision(1)][digito_verificador(1)]
        
        fecha = (factura.fecha_emision or datetime.now()).strftime('%d%m%Y')
        tipo_comprobante = '01'  # Factura
        
        # Obtener RUC desde configuración
        from inventario.models import Opciones
        opciones = Opciones.objects.first()
        if not opciones or not opciones.identificacion:
            raise ValueError("RUC no configurado en Opciones")
        ruc = opciones.identificacion.zfill(13)
        
        ambiente = '1' if self.ambiente == 'pruebas' else '2'
        serie = f"{factura.establecimiento}{factura.punto_emision}"
        secuencial = str(factura.secuencia).zfill(9)  # Usar 'secuencia' no 'secuencial'
        codigo_numerico = f"{random.randint(0, 99999999):08d}"  # Código aleatorio
        tipo_emision = '1'  # Normal
        
        clave_base = f"{fecha}{tipo_comprobante}{ruc}{ambiente}{serie}{secuencial}{codigo_numerico}{tipo_emision}"
        digito_verificador = self._calcular_digito_verificador(clave_base)
        
        return clave_base + digito_verificador
    
    def _calcular_digito_verificador(self, clave):
        """
        Calcula el dígito verificador para la clave de acceso según algoritmo SRI
        Usa coeficientes [2,3,4,5,6,7] aplicados de derecha a izquierda, repitiendo
        Algoritmo copiado del modelo Factura que ya funciona correctamente
        """
        # Convertir clave a lista de dígitos
        clave_lista = [int(d) for d in clave]
        pesos = [2, 3, 4, 5, 6, 7]
        total = 0
        peso_index = 0

        # Recorrer de derecha a izquierda
        for digito in reversed(clave_lista):
            total += digito * pesos[peso_index]
            peso_index = (peso_index + 1) % len(pesos)

        residuo = total % 11
        digito_verificador = 11 - residuo
        
        # Casos especiales según normativa SRI
        if digito_verificador == 11:
            return '0'
        elif digito_verificador == 10:
            return '1'
        else:
            return str(digito_verificador)
    
    def _actualizar_factura_con_resultado(self, factura, resultado, clave_acceso):
        """
        Actualiza la factura con el resultado del SRI
        
        Args:
            factura: Instancia de Factura
            resultado: Dict con resultado del SRI
            clave_acceso: Clave de acceso generada
        """
        factura.clave_acceso = clave_acceso
        
        if resultado['estado'] == 'AUTORIZADO':
            factura.estado = 'AUTORIZADO'
            factura.mensaje_sri = 'Comprobante autorizado'
            
            if resultado['autorizaciones']:
                aut = resultado['autorizaciones'][0]
                factura.numero_autorizacion = aut['numeroAutorizacion']
                factura.fecha_autorizacion = aut['fechaAutorizacion']
                
        elif resultado['estado'] == 'NO AUTORIZADO':
            factura.estado = 'RECHAZADO'
            factura.mensaje_sri = 'Comprobante rechazado por el SRI'
            
        elif resultado['estado'] == 'RECIBIDA':
            factura.estado = 'RECIBIDA'
            factura.mensaje_sri = 'Comprobante recibido por el SRI'
            
        else:  # ERROR o PENDIENTE
            factura.estado = 'ERROR'
            factura.mensaje_sri = f"Error: {resultado.get('mensajes', [{}])[0].get('mensaje', 'Error desconocido')}"
        
        # Guardar mensajes completos
        factura.mensaje_sri_detalle = str(resultado.get('mensajes', []))
        
        factura.save()
    
    def _generar_ride_autorizado(self, factura, resultado):
        """
        Genera el RIDE (Representación Impresa del Documento Electrónico)
        
        Args:
            factura: Instancia de Factura
            resultado: Dict con resultado del SRI
        """
        try:
            from .ride_generator import RIDEGenerator
            
            ride_gen = RIDEGenerator()
            pdf_content = ride_gen.generar_ride(factura, resultado)
            
            # Guardar RIDE
            ride_filename = f"RIDE_{factura.numero_factura}.pdf"
            ride_path = f"rides/{factura.empresa.ruc}/{ride_filename}"
            
            ride_file = ContentFile(pdf_content)
            saved_path = default_storage.save(ride_path, ride_file)
            
            # Actualizar factura con ruta del RIDE
            factura.ride_autorizado = saved_path
            factura.save()
            
            logger.info(f"RIDE generado: {saved_path}")
            
        except Exception as e:
            logger.error(f"Error generando RIDE: {e}")
    
    def consultar_estado_factura(self, factura_id):
        """
        Consulta el estado actual de una factura en el SRI
        
        Args:
            factura_id (int): ID de la factura
            
        Returns:
            dict: Estado actual
        """
        try:
            factura = Factura.objects.get(id=factura_id)
            
            if not factura.clave_acceso:
                return {
                    'success': False,
                    'message': 'La factura no tiene clave de acceso'
                }
            
            resultado = self.cliente.consultar_autorizacion(factura.clave_acceso)
            
            # Actualizar estado
            self._actualizar_factura_con_resultado(factura, resultado, factura.clave_acceso)
            
            return {
                'success': True,
                'resultado': resultado
            }
            
        except Factura.DoesNotExist:
            return {
                'success': False,
                'message': f'Factura con ID {factura_id} no encontrada'
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def reenviar_factura(self, factura_id):
        """
        Reenvía una factura que fue rechazada o tiene error
        
        Args:
            factura_id (int): ID de la factura
            
        Returns:
            dict: Resultado del reenvío
        """
        try:
            factura = Factura.objects.get(id=factura_id)
            
            # Verificar que pueda ser reenviada
            if factura.estado not in ['RECHAZADO', 'ERROR']:
                return {
                    'success': False,
                    'message': f'Solo se pueden reenviar facturas rechazadas o con error. Estado actual: {factura.estado}'
                }
            
            # Resetear estado
            factura.estado = 'PENDIENTE'
            factura.clave_acceso = None
            factura.numero_autorizacion = None
            factura.fecha_autorizacion = None
            factura.mensaje_sri = None
            factura.mensaje_sri_detalle = None
            factura.save()
            
            # Procesar nuevamente
            return self.procesar_factura(factura_id)
            
        except Factura.DoesNotExist:
            return {
                'success': False,
                'message': f'Factura con ID {factura_id} no encontrada'
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }

# Funciones auxiliares para uso en Django Admin o Views
def procesar_factura_async(factura_id):
    """
    Función para procesar facturas de forma asíncrona (ej: Celery)
    """
    integration = SRIIntegration()
    return integration.procesar_factura(factura_id)

def consultar_lote_facturas():
    """
    Consulta el estado de todas las facturas pendientes
    """
    from inventario.models import Factura
    
    facturas_pendientes = Factura.objects.filter(estado__in=['RECIBIDA', 'PENDIENTE'])
    integration = SRIIntegration()
    
    resultados = []
    for factura in facturas_pendientes:
        resultado = integration.consultar_estado_factura(factura.id)
        resultados.append({
            'factura_id': factura.id,
            'numero': factura.numero_factura,
            'resultado': resultado
        })
    
    return resultados