import logging
import base64
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
import zeep
from zeep import Client
from zeep.transports import Transport
from zeep.exceptions import Fault, TransportError

# ✅ CONFIGURAR LOGGING DE ZEEP PARA EVITAR SPAM DE DEBUG
logging.getLogger('zeep').setLevel(logging.WARNING)
logging.getLogger('zeep.xsd.schema').setLevel(logging.WARNING)
logging.getLogger('zeep.transports').setLevel(logging.WARNING)
logging.getLogger('zeep.wsdl.wsdl').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class SRIClient:
    """
    Cliente para integración con el Servicio de Rentas Internas (SRI) de Ecuador
    mediante servicios web SOAP para facturación electrónica.
    """
    
    # URLs de los servicios web del SRI - Actualizadas 2024/2025
    WSDL_RECEPCION_PRUEBAS = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl"
    WSDL_AUTORIZACION_PRUEBAS = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    
    WSDL_RECEPCION_PRODUCCION = "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl"
    WSDL_AUTORIZACION_PRODUCCION = "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    
    def __init__(self, ambiente='pruebas', timeout=30):
        """
        Inicializa el cliente SRI.
        
        Args:
            ambiente (str): 'pruebas' o 'produccion'
            timeout (int): Tiempo de espera para las peticiones en segundos
        """
        self.ambiente = ambiente
        self.timeout = timeout
        
        # Configurar URLs según ambiente
        if ambiente == 'produccion':
            self.wsdl_recepcion = self.WSDL_RECEPCION_PRODUCCION
            self.wsdl_autorizacion = self.WSDL_AUTORIZACION_PRODUCCION
        else:
            self.wsdl_recepcion = self.WSDL_RECEPCION_PRUEBAS
            self.wsdl_autorizacion = self.WSDL_AUTORIZACION_PRUEBAS
        
        # Configurar transporte con timeout
        transport = Transport(timeout=timeout)
        
        # Crear clientes SOAP
        try:
            self.cliente_recepcion = Client(wsdl=self.wsdl_recepcion, transport=transport)
            self.cliente_autorizacion = Client(wsdl=self.wsdl_autorizacion, transport=transport)
            logger.info(f"Clientes SRI inicializados correctamente - Ambiente: {ambiente}")
        except Exception as e:
            logger.error(f"Error al inicializar clientes SRI: {e}")
            raise
    
    def enviar_comprobante(self, xml_content: str, clave_acceso: str) -> Dict:
        """
        Envía un comprobante electrónico al servicio de recepción del SRI.
        
        Args:
            xml_content (str): Contenido XML del comprobante
            clave_acceso (str): Clave de acceso del comprobante
            
        Returns:
            Dict: Respuesta del SRI con estado y mensajes
        """
        try:
            # Codificar XML en base64
            xml_base64 = base64.b64encode(xml_content.encode('utf-8')).decode('utf-8')
            
            # Llamar al servicio de recepción
            response = self.cliente_recepcion.service.validarComprobante(xml_base64)
            
            # Procesar respuesta
            resultado = self._procesar_respuesta_recepcion(response)
            
            logger.info(f"Comprobante enviado - Clave: {clave_acceso} - Estado: {resultado.get('estado')}")
            return resultado
            
        except Fault as e:
            logger.error(f"Error SOAP al enviar comprobante: {e}")
            return {
                'estado': 'ERROR',
                'mensajes': [{
                    'identificador': 'SOAP_ERROR',
                    'mensaje': str(e),
                    'tipo': 'ERROR'
                }],
                'clave_acceso': clave_acceso
            }
        except Exception as e:
            logger.error(f"Error al enviar comprobante: {e}")
            return {
                'estado': 'ERROR',
                'mensajes': [{
                    'identificador': 'CLIENT_ERROR',
                    'mensaje': str(e),
                    'tipo': 'ERROR'
                }],
                'clave_acceso': clave_acceso
            }
    
    def consultar_autorizacion(self, clave_acceso: str) -> Dict:
        """
        Consulta la autorización de un comprobante en el SRI.
        
        Args:
            clave_acceso (str): Clave de acceso del comprobante
            
        Returns:
            Dict: Respuesta con estado de autorización y detalles
        """
        try:
            # Llamar al servicio de autorización
            response = self.cliente_autorizacion.service.autorizacionComprobante(clave_acceso)
            
            # Procesar respuesta
            resultado = self._procesar_respuesta_autorizacion(response)
            
            logger.info(f"Consulta autorización - Clave: {clave_acceso} - Estado: {resultado.get('estado')}")
            return resultado
            
        except Fault as e:
            logger.error(f"Error SOAP al consultar autorización: {e}")
            return {
                'estado': 'ERROR',
                'mensajes': [{
                    'identificador': 'SOAP_ERROR',
                    'mensaje': str(e),
                    'tipo': 'ERROR'
                }],
                'clave_acceso': clave_acceso
            }
        except Exception as e:
            logger.error(f"Error al consultar autorización: {e}")
            return {
                'estado': 'ERROR',
                'mensajes': [{
                    'identificador': 'CLIENT_ERROR',
                    'mensaje': str(e),
                    'tipo': 'ERROR'
                }],
                'clave_acceso': clave_acceso
            }
    
    def procesar_comprobante_completo(self, xml_content: str, clave_acceso: str, 
                                    max_intentos: int = 3, espera_segundos: int = 3) -> Dict:
        """
        Procesa un comprobante completo: envío y consulta de autorización.
        
        Args:
            xml_content (str): Contenido XML del comprobante
            clave_acceso (str): Clave de acceso del comprobante
            max_intentos (int): Máximo de intentos para consultar autorización
            espera_segundos (int): Segundos entre intentos
            
        Returns:
            Dict: Resultado final del procesamiento
        """
        logger.info(f"Iniciando procesamiento completo - Clave: {clave_acceso}")
        
        # Paso 1: Enviar comprobante
        resultado_envio = self.enviar_comprobante(xml_content, clave_acceso)
        
        if resultado_envio['estado'] != 'RECIBIDA':
            logger.warning(f"Comprobante no fue recibido: {resultado_envio}")
            return resultado_envio
        
        # Paso 2: Consultar autorización con reintentos
        for intento in range(1, max_intentos + 1):
            logger.info(f"Consultando autorización - Intento {intento}/{max_intentos}")
            
            resultado_autorizacion = self.consultar_autorizacion(clave_acceso)
            
            if resultado_autorizacion['estado'] in ['AUTORIZADO', 'NO AUTORIZADO']:
                return resultado_autorizacion
            
            if intento < max_intentos:
                import time
                time.sleep(espera_segundos)
        
        # Si no se obtuvo respuesta después de los intentos
        return {
            'estado': 'PENDIENTE',
            'mensajes': [{
                'identificador': 'TIMEOUT',
                'mensaje': f'No se pudo obtener autorización después de {max_intentos} intentos',
                'tipo': 'ADVERTENCIA'
            }],
            'clave_acceso': clave_acceso
        }
    
    def _is_iterable_safe(self, obj):
        """Verifica si un objeto es iterable de forma segura (excluyendo strings)"""
        try:
            # Verificar si es None
            if obj is None:
                return False
            # Verificar si es string (no queremos iterar sobre caracteres)
            if isinstance(obj, (str, bytes)):
                return False
            # Verificar si es iterable
            iter(obj)
            return True
        except TypeError:
            return False
    
    def _procesar_respuesta_recepcion(self, response) -> Dict:
        """Procesa la respuesta del servicio de recepción."""
        try:
            # Log de la respuesta para debugging
            logger.debug(f"Respuesta recibida: {str(response)}")
            
            # Manejar caso donde response es None
            if response is None:
                return {
                    'estado': 'ERROR',
                    'mensajes': [{
                        'identificador': 'NULL_RESPONSE',
                        'mensaje': 'Respuesta nula del servicio SRI',
                        'tipo': 'ERROR'
                    }],
                    'raw_response': 'None'
                }
            
            # Extraer información de la respuesta
            estado = getattr(response, 'estado', 'ERROR')
            mensajes = []
            
            if hasattr(response, 'comprobantes') and response.comprobantes:
                # Asegurar que comprobantes sea iterable
                comprobantes = response.comprobantes if self._is_iterable_safe(response.comprobantes) else [response.comprobantes]
                
                for comprobante in comprobantes:
                    if hasattr(comprobante, 'mensajes') and comprobante.mensajes:
                        # Asegurar que mensajes sea iterable
                        mensajes_comprobante = comprobante.mensajes if self._is_iterable_safe(comprobante.mensajes) else [comprobante.mensajes]
                        
                        for msg in mensajes_comprobante:
                            mensajes.append({
                                'identificador': getattr(msg, 'identificador', ''),
                                'mensaje': getattr(msg, 'mensaje', ''),
                                'tipo': getattr(msg, 'tipo', ''),
                                'informacionAdicional': getattr(msg, 'informacionAdicional', '')
                            })
            
            return {
                'estado': estado,
                'mensajes': mensajes,
                'raw_response': str(response)
            }
            
        except Exception as e:
            logger.error(f"Error procesando respuesta recepción: {e}")
            return {
                'estado': 'ERROR',
                'mensajes': [{
                    'identificador': 'PARSE_ERROR',
                    'mensaje': f'Error al procesar respuesta: {str(e)}',
                    'tipo': 'ERROR'
                }]
            }
    
    def _procesar_respuesta_autorizacion(self, response) -> Dict:
        """Procesa la respuesta del servicio de autorización."""
        try:
            # Log de la respuesta para debugging
            logger.debug(f"Respuesta autorización recibida: {str(response)}")
            
            # Manejar caso donde response es None
            if response is None:
                return {
                    'estado': 'ERROR',
                    'mensajes': [{
                        'identificador': 'NULL_RESPONSE',
                        'mensaje': 'Respuesta nula del servicio de autorización SRI',
                        'tipo': 'ERROR'
                    }],
                    'raw_response': 'None'
                }
            
            autorizaciones = []
            mensajes = []
            
            # Verificar si existe el atributo autorizaciones
            if hasattr(response, 'autorizaciones'):
                if response.autorizaciones is None:
                    # Caso específico: SRI responde con autorizaciones: None
                    # Esto significa que el comprobante aún no está autorizado
                    mensajes.append({
                        'identificador': 'NO_AUTORIZADO',
                        'mensaje': 'El comprobante no ha sido autorizado aún o no existe',
                        'tipo': 'INFORMACION',
                        'informacionAdicional': 'Respuesta del SRI indica autorizaciones: None'
                    })
                    estado_final = 'PENDIENTE'
                elif response.autorizaciones:
                    # Asegurar que autorizaciones sea iterable
                    autorizaciones_list = response.autorizaciones if self._is_iterable_safe(response.autorizaciones) else [response.autorizaciones]
                    
                    for aut in autorizaciones_list:
                        autorizacion = {
                            'estado': getattr(aut, 'estado', 'ERROR'),
                            'numeroAutorizacion': getattr(aut, 'numeroAutorizacion', ''),
                            'fechaAutorizacion': getattr(aut, 'fechaAutorizacion', ''),
                            'ambiente': getattr(aut, 'ambiente', ''),
                            'comprobante': getattr(aut, 'comprobante', ''),
                            'mensajes': []
                        }
                        
                        if hasattr(aut, 'mensajes') and aut.mensajes:
                            # Asegurar que mensajes sea iterable
                            mensajes_aut = aut.mensajes if self._is_iterable_safe(aut.mensajes) else [aut.mensajes]
                            
                            for msg in mensajes_aut:
                                mensaje = {
                                    'identificador': getattr(msg, 'identificador', ''),
                                    'mensaje': getattr(msg, 'mensaje', ''),
                                    'tipo': getattr(msg, 'tipo', ''),
                                    'informacionAdicional': getattr(msg, 'informacionAdicional', '')
                                }
                                autorizacion['mensajes'].append(mensaje)
                                mensajes.append(mensaje)
                        
                        autorizaciones.append(autorizacion)
                    estado_final = autorizaciones[0]['estado'] if autorizaciones else 'ERROR'
                else:
                    # Caso donde autorizaciones existe pero está vacío
                    estado_final = 'PENDIENTE'
            else:
                # Caso donde no existe el atributo autorizaciones
                mensajes.append({
                    'identificador': 'ESTRUCTURA_INVALIDA',
                    'mensaje': 'Respuesta del SRI no contiene información de autorizaciones',
                    'tipo': 'ERROR'
                })
                estado_final = 'ERROR'
            
            return {
                'estado': estado_final,
                'autorizaciones': autorizaciones,
                'mensajes': mensajes,
                'raw_response': str(response)
            }
            
        except Exception as e:
            logger.error(f"Error procesando respuesta autorización: {e}")
            return {
                'estado': 'ERROR',
                'mensajes': [{
                    'identificador': 'PARSE_ERROR',
                    'mensaje': f'Error al procesar respuesta: {str(e)}',
                    'tipo': 'ERROR'
                }]
            }
    
    def verificar_servicio(self) -> Dict:
        """
        Verifica la disponibilidad de los servicios del SRI.
        
        Returns:
            Dict: Estado de los servicios
        """
        resultado = {
            'recepcion': {'disponible': False, 'error': None},
            'autorizacion': {'disponible': False, 'error': None}
        }
        
        # Verificar servicio de recepción
        try:
            self.cliente_recepcion.service.validarComprobante(b'')
            resultado['recepcion']['disponible'] = True
        except Exception as e:
            resultado['recepcion']['error'] = str(e)
        
        # Verificar servicio de autorización
        try:
            self.cliente_autorizacion.service.autorizacionComprobante('')
            resultado['autorizacion']['disponible'] = True
        except Exception as e:
            resultado['autorizacion']['error'] = str(e)
        
        return resultado