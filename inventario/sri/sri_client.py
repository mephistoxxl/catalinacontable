import logging
import base64
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from django.conf import settings
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
    
    def __init__(self, ambiente='pruebas', timeout=None):
        """
        Inicializa el cliente SRI.

        Args:
            ambiente (str): 'pruebas' o 'produccion'
            timeout (int, optional): Tiempo de espera para las peticiones en segundos
        """
        self.ambiente = ambiente
        self.timeout = timeout if timeout is not None else getattr(settings, 'SRI_TIMEOUT', 30)
        
        # Configurar URLs según ambiente
        if ambiente == 'produccion':
            self.wsdl_recepcion = self.WSDL_RECEPCION_PRODUCCION
            self.wsdl_autorizacion = self.WSDL_AUTORIZACION_PRODUCCION
        else:
            self.wsdl_recepcion = self.WSDL_RECEPCION_PRUEBAS
            self.wsdl_autorizacion = self.WSDL_AUTORIZACION_PRUEBAS
        
        # Configurar transporte con timeout
        transport = Transport(timeout=self.timeout)
        
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
            try:
                response = self.cliente_recepcion.service.validarComprobante(xml_base64)
            except (Timeout, ConnectionError) as e:
                logger.error(f"Error de conexión al enviar comprobante: {e}")
                return {
                    'estado': 'ERROR',
                    'mensajes': [{
                        'identificador': 'CONNECTION_ERROR',
                        'mensaje': f'Error de conexión con el servicio SRI: {e}',
                        'tipo': 'ERROR'
                    }],
                    'clave_acceso': clave_acceso
                }

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
            try:
                response = self.cliente_autorizacion.service.autorizacionComprobante(clave_acceso)
            except (Timeout, ConnectionError) as e:
                logger.error(f"Error de conexión al consultar autorización: {e}")
                return {
                    'estado': 'ERROR',
                    'mensajes': [{
                        'identificador': 'CONNECTION_ERROR',
                        'mensaje': f'Error de conexión con el servicio SRI: {e}',
                        'tipo': 'ERROR'
                    }],
                    'clave_acceso': clave_acceso
                }

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
            # 🔧 FIX: No considerar los dict como iterables válidos para listas de elementos
            if isinstance(obj, dict):
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

            def _get(obj, key, default=None):
                if obj is None:
                    return default
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            def _normalizar_comprobantes(comprobantes_node):
                """Normaliza la estructura de zeep: response.comprobantes.comprobante -> lista."""
                if comprobantes_node is None:
                    return []

                if isinstance(comprobantes_node, dict) and 'comprobante' in comprobantes_node:
                    comprobantes_node = comprobantes_node.get('comprobante')

                if hasattr(comprobantes_node, 'comprobante'):
                    try:
                        comprobantes_node = getattr(comprobantes_node, 'comprobante')
                    except Exception:
                        pass

                if comprobantes_node is None:
                    return []

                return comprobantes_node if self._is_iterable_safe(comprobantes_node) else [comprobantes_node]

            def _normalizar_mensajes(mensajes_node):
                """Normaliza mensajes: comprobante.mensajes.mensaje -> lista de items."""
                if mensajes_node is None:
                    return []

                if isinstance(mensajes_node, dict) and 'mensaje' in mensajes_node:
                    mensajes_node = mensajes_node.get('mensaje')

                if hasattr(mensajes_node, 'mensaje'):
                    try:
                        mensajes_node = getattr(mensajes_node, 'mensaje')
                    except Exception:
                        pass

                if mensajes_node is None:
                    return []

                return mensajes_node if self._is_iterable_safe(mensajes_node) else [mensajes_node]
            
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
            estado = _get(response, 'estado', 'ERROR')
            mensajes = []

            comprobantes_node = _get(response, 'comprobantes', None)
            for comprobante in _normalizar_comprobantes(comprobantes_node):
                mensajes_node = _get(comprobante, 'mensajes', None)
                for msg in _normalizar_mensajes(mensajes_node):
                    mensajes.append({
                        'identificador': _get(msg, 'identificador', ''),
                        'mensaje': _get(msg, 'mensaje', ''),
                        'tipo': _get(msg, 'tipo', ''),
                        'informacionAdicional': _get(msg, 'informacionAdicional', '')
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

            def _normalizar_mensajes(mensajes_aut):
                """Zeep suele devolver mensajes como mensajes.mensaje; normalizar a lista de items."""
                if mensajes_aut is None:
                    return []

                # dict con clave 'mensaje'
                if isinstance(mensajes_aut, dict) and 'mensaje' in mensajes_aut:
                    mensajes_aut = mensajes_aut.get('mensaje')

                # objeto con atributo .mensaje
                if hasattr(mensajes_aut, 'mensaje'):
                    try:
                        mensajes_aut = getattr(mensajes_aut, 'mensaje')
                    except Exception:
                        pass

                if mensajes_aut is None:
                    return []

                return mensajes_aut if self._is_iterable_safe(mensajes_aut) else [mensajes_aut]

            # Obtener dato de autorizaciones desde dict u objeto
            if isinstance(response, dict):
                autorizaciones_data = response.get('autorizaciones')
            else:
                autorizaciones_data = getattr(response, 'autorizaciones', None)

            if autorizaciones_data is None:
                # Caso específico: SRI responde con autorizaciones: None
                mensajes.append({
                    'identificador': 'NO_AUTORIZADO',
                    'mensaje': 'El comprobante no ha sido autorizado aún o no existe',
                    'tipo': 'INFORMACION',
                    'informacionAdicional': 'Respuesta del SRI indica autorizaciones: None'
                })
                estado_final = 'PENDIENTE'
            elif autorizaciones_data:
                # Asegurar que autorizaciones sea iterable y manejar distintas estructuras
                if isinstance(autorizaciones_data, dict) and 'autorizacion' in autorizaciones_data:
                    autorizaciones_items = autorizaciones_data['autorizacion']
                elif hasattr(autorizaciones_data, 'autorizacion'):
                    autorizaciones_items = getattr(autorizaciones_data, 'autorizacion')
                else:
                    autorizaciones_items = autorizaciones_data

                autorizaciones_list = autorizaciones_items if self._is_iterable_safe(autorizaciones_items) else [autorizaciones_items]

                for aut in autorizaciones_list:
                    if isinstance(aut, dict):
                        estado = aut.get('estado', 'ERROR')
                        numero = aut.get('numeroAutorizacion', '')
                        fecha = aut.get('fechaAutorizacion', '')
                        ambiente = aut.get('ambiente', '')
                        comprobante = aut.get('comprobante', '')
                        mensajes_aut = aut.get('mensajes')
                    else:
                        estado = getattr(aut, 'estado', 'ERROR')
                        numero = getattr(aut, 'numeroAutorizacion', '')
                        fecha = getattr(aut, 'fechaAutorizacion', '')
                        ambiente = getattr(aut, 'ambiente', '')
                        comprobante = getattr(aut, 'comprobante', '')
                        mensajes_aut = getattr(aut, 'mensajes', None)

                    autorizacion = {
                        'estado': estado,
                        'numeroAutorizacion': numero,
                        'fechaAutorizacion': fecha,
                        'ambiente': ambiente,
                        'comprobante': comprobante,
                        'mensajes': []
                    }

                    if mensajes_aut:
                        for msg in _normalizar_mensajes(mensajes_aut):
                            if isinstance(msg, dict):
                                mensaje = {
                                    'identificador': msg.get('identificador', ''),
                                    'mensaje': msg.get('mensaje', ''),
                                    'tipo': msg.get('tipo', ''),
                                    'informacionAdicional': msg.get('informacionAdicional', '')
                                }
                            else:
                                mensaje = {
                                    'identificador': getattr(msg, 'identificador', ''),
                                    'mensaje': getattr(msg, 'mensaje', ''),
                                    'tipo': getattr(msg, 'tipo', ''),
                                    'informacionAdicional': getattr(msg, 'informacionAdicional', '')
                                }

                            # Evitar agregar mensajes totalmente vacíos
                            if not any((mensaje.get('identificador'), mensaje.get('mensaje'), mensaje.get('tipo'), mensaje.get('informacionAdicional'))):
                                continue
                            autorizacion['mensajes'].append(mensaje)
                            mensajes.append(mensaje)

                    autorizaciones.append(autorizacion)

                estado_final = autorizaciones[0]['estado'] if autorizaciones else 'ERROR'
            else:
                # Caso donde autorizaciones existe pero está vacío
                estado_final = 'PENDIENTE'

            if not autorizaciones_data:
                # Si no se pudo procesar, registrar estructura inválida
                if autorizaciones_data is None and not mensajes:
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