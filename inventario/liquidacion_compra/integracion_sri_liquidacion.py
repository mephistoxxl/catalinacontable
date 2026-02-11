"""
Integración con el SRI para Liquidaciones de Compra (codDoc 03)
Reutiliza el cliente SRI existente sin modificar la integración de facturas.
"""
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, Tuple

from django.utils import timezone
from django.db import transaction

from ..sri.sri_client import SRIClient
from ..sri.firmador_xades_sri_simple import FirmadorXAdESSRIEcuador
from .xml_generator_liquidacion import LiquidacionXMLGenerator
from .models import LiquidacionCompra, LiquidacionLogCambioEstado

logger = logging.getLogger(__name__)


class IntegracionSRILiquidacion:
    """
    Servicio de integración con el SRI específico para Liquidaciones de Compra.
    Maneja el flujo completo: XML → Firma → Recepción → Autorización.
    """

    def __init__(self, empresa):
        """
        Inicializa la integración SRI para una empresa específica.
        
        Args:
            empresa: Instancia de Empresa con opciones de facturación configuradas
        """
        self.empresa = empresa
        self.opciones = empresa.opciones.first() if hasattr(empresa, 'opciones') else None
        
        if not self.opciones:
            raise ValueError(f"La empresa {empresa.ruc} no tiene opciones de facturación configuradas")
        
        # Determinar ambiente (1=pruebas, 2=producción)
        ambiente_sri = 'produccion' if self.opciones.tipo_ambiente == '2' else 'pruebas'
        
        # Inicializar componentes
        self.cliente_sri = SRIClient(ambiente=ambiente_sri)
        self.generador_xml = LiquidacionXMLGenerator()
        
        logger.info(f"Integración SRI Liquidación inicializada - Empresa: {empresa.ruc} - Ambiente: {ambiente_sri}")

    def procesar_liquidacion_completa(
        self,
        liquidacion: LiquidacionCompra,
        *,
        enviar_solo: bool = False,
        max_envio_intentos: int = 8,
        espera_envio_seg: int = 2,
    ) -> Dict:
        """
        Procesa el flujo completo de una liquidación: generar XML, firmar, enviar y autorizar.
        
        Args:
            liquidacion: Instancia de LiquidacionCompra
            
        Returns:
            Dict con resultado del procesamiento:
            {
                'exito': bool,
                'estado': str,
                'numero_autorizacion': str (si está autorizada),
                'fecha_autorizacion': datetime (si está autorizada),
                'mensajes': list,
                'xml_firmado': str,
                'xml_autorizado': str (si está autorizada)
            }
        """
        try:
            with transaction.atomic():
                # 1. Validar estado
                if liquidacion.estado not in ['BORRADOR', 'LISTA']:
                    return {
                        'exito': False,
                        'estado': 'ERROR',
                        'mensajes': [f'La liquidación está en estado {liquidacion.estado} y no puede procesarse']
                    }
                
                # 2. Generar clave de acceso si no existe
                if not liquidacion.clave_acceso:
                    liquidacion.generar_clave_acceso()
                    liquidacion.save(update_fields=['clave_acceso'])
                
                # 3. Generar XML
                logger.info(f"Generando XML para liquidación {liquidacion.clave_acceso}")
                xml_sin_firmar = self.generador_xml.generar_xml_liquidacion(liquidacion)
                
                # 4. Firmar XML
                logger.info(f"Firmando XML para liquidación {liquidacion.clave_acceso}")
                resultado_firma = self._firmar_xml(xml_sin_firmar)
                
                if not resultado_firma['exito']:
                    self._registrar_log(liquidacion, 'ERROR', '', 
                                       f"Error al firmar: {resultado_firma.get('mensaje')}")
                    return {
                        'exito': False,
                        'estado': 'ERROR',
                        'mensajes': [resultado_firma.get('mensaje', 'Error desconocido al firmar')]
                    }
                
                xml_firmado = resultado_firma['xml_firmado']
                
                # Actualizar estado a FIRMADA
                liquidacion.estado = 'FIRMADA'
                liquidacion.xml_firmado = xml_firmado
                liquidacion.save(update_fields=['estado', 'xml_firmado'])
                self._registrar_log(liquidacion, 'FIRMADA', '', 'XML firmado correctamente')
                
                # 5. Enviar al SRI (reintentar hasta RECIBIDA)
                logger.info(f"Enviando liquidación {liquidacion.clave_acceso} al SRI")
                resultado_envio = None

                for intento_envio in range(max_envio_intentos):
                    resultado_envio = self.cliente_sri.enviar_comprobante(
                        xml_content=xml_firmado,
                        clave_acceso=liquidacion.clave_acceso
                    )
                    estado_envio = (resultado_envio or {}).get('estado')

                    logger.info(
                        "Envio SRI LC intento %s/%s - clave=%s - estado=%s - mensajes=%s",
                        intento_envio + 1,
                        max_envio_intentos,
                        liquidacion.clave_acceso,
                        estado_envio,
                        (resultado_envio or {}).get('mensajes', []),
                    )

                    if estado_envio == 'RECIBIDA':
                        break

                    if estado_envio == 'DEVUELTA':
                        # DEVUELTA es rechazo en recepción, no reintentar
                        break

                    if estado_envio == 'ERROR' and self._mensajes_indican_en_procesamiento(
                        (resultado_envio or {}).get('mensajes', [])
                    ):
                        estado_envio = 'EN PROCESAMIENTO'

                    if intento_envio < max_envio_intentos - 1:
                        logger.info(
                            "Liquidación %s no recibida (estado=%s), reintento %s/%s",
                            liquidacion.clave_acceso,
                            estado_envio,
                            intento_envio + 1,
                            max_envio_intentos,
                        )
                        time.sleep(espera_envio_seg)

                if (resultado_envio or {}).get('estado') == 'RECIBIDA':
                    liquidacion.estado = 'ENVIADA'
                    liquidacion.estado_sri = 'RECIBIDA'
                    liquidacion.save(update_fields=['estado', 'estado_sri'])
                    self._registrar_log(liquidacion, 'ENVIADA', 'RECIBIDA', 
                                       'Comprobante recibido por el SRI')

                    if enviar_solo:
                        return {
                            'exito': True,
                            'estado': 'RECIBIDA',
                            'mensajes': ['Comprobante recibido por el SRI'],
                            'xml_firmado': xml_firmado,
                        }
                    
                    # 6. Consultar autorización
                    logger.info(f"Consultando autorización para liquidación {liquidacion.clave_acceso}")
                    resultado_autorizacion = self._consultar_autorizacion(liquidacion)
                    
                    return resultado_autorizacion
                    
                else:
                    # Error en recepción
                    mensajes = resultado_envio.get('mensajes', [])
                    mensaje_error = self._formatear_mensajes_sri(mensajes)

                    # Caso especial: SRI indica secuencial duplicado (código 45)
                    if self._mensajes_indican_secuencial_registrado(mensajes):
                        numero = f"{liquidacion.serie_formateada}-{liquidacion.secuencia_formateada}"
                        mensaje_error = (
                            "El SRI reporta que el secuencial ya está registrado para esta serie. "
                            f"Número: {numero}. "
                            "Esto suele ocurrir cuando la secuencia local está desfasada (por migración, reinicio, "
                            "o porque ya se emitieron documentos con esa serie fuera del sistema). "
                            "Solución: en Configuración → Secuencias, ajuste el 'siguiente secuencial' de "
                            "Liquidación de Compra (03) a un número mayor al último emitido en el SRI para esa serie "
                            "y vuelva a emitir una nueva liquidación."
                        )
                    
                    if enviar_solo:
                        estado_envio = (resultado_envio or {}).get('estado') or ''
                        if estado_envio == 'DEVUELTA':
                            liquidacion.estado = 'RECHAZADA'
                            liquidacion.estado_sri = 'RECHAZADA'
                            liquidacion.mensaje_sri = mensaje_error
                            liquidacion.save(update_fields=['estado', 'estado_sri', 'mensaje_sri'])
                            self._registrar_log(liquidacion, 'RECHAZADA', 'RECHAZADA', mensaje_error)
                            return {
                                'exito': False,
                                'estado': 'RECHAZADA',
                                'mensajes': mensajes,
                                'xml_firmado': xml_firmado,
                            }

                        liquidacion.estado_sri = 'PENDIENTE'
                        liquidacion.mensaje_sri = mensaje_error or 'Envío en procesamiento en el SRI'
                        liquidacion.save(update_fields=['estado_sri', 'mensaje_sri'])
                        self._registrar_log(liquidacion, 'FIRMADA', 'PENDIENTE', liquidacion.mensaje_sri)
                        return {
                            'exito': False,
                            'estado': 'PENDIENTE',
                            'mensajes': mensajes or ['Envío en procesamiento. Se reintentará.'],
                            'xml_firmado': xml_firmado,
                        }

                    liquidacion.estado = 'RECHAZADA'
                    liquidacion.estado_sri = 'RECHAZADA'
                    liquidacion.mensaje_sri = mensaje_error
                    liquidacion.save(update_fields=['estado', 'estado_sri', 'mensaje_sri'])
                    self._registrar_log(liquidacion, 'RECHAZADA', 'RECHAZADA', mensaje_error)

                    return {
                        'exito': False,
                        'estado': 'RECHAZADA',
                        'mensajes': mensajes,
                        'xml_firmado': xml_firmado
                    }
                    
        except Exception as e:
            logger.error(f"Error procesando liquidación {liquidacion.id}: {e}", exc_info=True)
            self._registrar_log(liquidacion, 'ERROR', 'ERROR', str(e))
            return {
                'exito': False,
                'estado': 'ERROR',
                'mensajes': [str(e)]
            }

    def enviar_liquidacion(self, liquidacion: LiquidacionCompra) -> Dict:
        """Genera, firma y envia la liquidacion al SRI (solo recepcion)."""
        try:
            estado_sri = (liquidacion.estado_sri or '').strip().upper()
            if estado_sri in {'AUTORIZADA', 'AUTORIZADO', 'RECHAZADA', 'NO_AUTORIZADA', 'NO AUTORIZADO', 'NO_AUTORIZADA'}:
                return {
                    'exito': True,
                    'estado': estado_sri,
                    'mensajes': [f'La liquidacion ya esta {estado_sri} en el SRI'],
                }

            estado_doc = (liquidacion.estado or '').strip().upper()
            if estado_doc not in {'BORRADOR', 'LISTA', 'FIRMADA', 'ENVIADA'}:
                return {
                    'exito': False,
                    'estado': 'ERROR',
                    'mensajes': [f'Estado invalido para envio: {liquidacion.estado}'],
                }

            if not liquidacion.clave_acceso:
                liquidacion.generar_clave_acceso()
                liquidacion.save(update_fields=['clave_acceso'])

            if not liquidacion.xml_firmado:
                xml_sin_firmar = self.generador_xml.generar_xml_liquidacion(liquidacion)
                resultado_firma = self._firmar_xml(xml_sin_firmar)
                if not resultado_firma['exito']:
                    self._registrar_log(liquidacion, 'ERROR', '', f"Error al firmar: {resultado_firma.get('mensaje')}")
                    return {
                        'exito': False,
                        'estado': 'ERROR',
                        'mensajes': [resultado_firma.get('mensaje', 'Error desconocido al firmar')],
                    }

                liquidacion.estado = 'FIRMADA'
                liquidacion.xml_firmado = resultado_firma['xml_firmado']
                liquidacion.save(update_fields=['estado', 'xml_firmado'])
                self._registrar_log(liquidacion, 'FIRMADA', '', 'XML firmado correctamente')

            xml_firmado = liquidacion.xml_firmado
            resultado_envio = self.cliente_sri.enviar_comprobante(
                xml_content=xml_firmado,
                clave_acceso=liquidacion.clave_acceso,
            )
            estado_envio = (resultado_envio or {}).get('estado') or 'ERROR'
            mensajes = (resultado_envio or {}).get('mensajes', [])

            if estado_envio == 'RECIBIDA':
                liquidacion.estado = 'ENVIADA'
                liquidacion.estado_sri = 'RECIBIDA'
                liquidacion.save(update_fields=['estado', 'estado_sri'])
                self._registrar_log(liquidacion, 'ENVIADA', 'RECIBIDA', 'Comprobante recibido por el SRI')
                return {
                    'exito': True,
                    'estado': 'RECIBIDA',
                    'mensajes': ['Comprobante recibido por el SRI'],
                }

            if estado_envio == 'DEVUELTA':
                mensaje_error = self._formatear_mensajes_sri(mensajes)
                liquidacion.estado = 'RECHAZADA'
                liquidacion.estado_sri = 'RECHAZADA'
                liquidacion.mensaje_sri = mensaje_error
                liquidacion.save(update_fields=['estado', 'estado_sri', 'mensaje_sri'])
                self._registrar_log(liquidacion, 'RECHAZADA', 'RECHAZADA', mensaje_error)
                return {
                    'exito': False,
                    'estado': 'RECHAZADA',
                    'mensajes': mensajes,
                }

            liquidacion.estado_sri = 'PENDIENTE'
            if mensajes:
                liquidacion.mensaje_sri = self._formatear_mensajes_sri(mensajes)
            liquidacion.save(update_fields=['estado_sri', 'mensaje_sri'])
            self._registrar_log(liquidacion, 'FIRMADA', 'PENDIENTE', liquidacion.mensaje_sri or 'En envio')
            return {
                'exito': False,
                'estado': 'PENDIENTE',
                'mensajes': mensajes or ['En envio. Se reintentara.'],
            }

        except Exception as e:
            logger.error(f"Error enviando liquidacion {liquidacion.id}: {e}", exc_info=True)
            self._registrar_log(liquidacion, 'ERROR', 'ERROR', str(e))
            return {
                'exito': False,
                'estado': 'ERROR',
                'mensajes': [str(e)],
            }

    def _firmar_xml(self, xml_content: str) -> Dict:
        """
        Firma el XML con la firma electrónica de la empresa.
        
        Args:
            xml_content: XML sin firmar
            
        Returns:
            Dict con resultado de la firma
        """
        try:
            # Validar configuración de firma
            if not self.opciones.firma_electronica:
                return {
                    'exito': False,
                    'mensaje': 'No hay firma electrónica configurada'
                }
            
            logger.info(f"🔏 Firmando liquidación de compra con firmador SRI Ecuador")
            
            # Leer el contenido del archivo P12
            try:
                with self.opciones.firma_electronica.open('rb') as f:
                    p12_content = f.read()
                logger.info(f"✅ Firma electrónica leída: {len(p12_content)} bytes")
            except Exception as e:
                logger.error(f"❌ Error leyendo firma electrónica: {e}")
                return {
                    'exito': False,
                    'mensaje': f'No se pudo leer el certificado de firma: {str(e)}'
                }
            
            password = self.opciones.password_firma
            
            # Usar firmador XAdES-BES simplificado (el mismo que guías de remisión)
            firmador = FirmadorXAdESSRIEcuador(p12_content, password)
            xml_firmado = firmador.firmar_xml(xml_content)
            
            logger.info("✅ XML de liquidación firmado exitosamente con XAdES-BES SRI Ecuador")
            return {
                'exito': True,
                'xml_firmado': xml_firmado
            }
            
        except Exception as e:
            logger.error(f"❌ Error firmando XML de liquidación: {e}", exc_info=True)
            return {
                'exito': False,
                'mensaje': f'Error al firmar XML: {str(e)}'
            }

    def _consultar_autorizacion(self, liquidacion: LiquidacionCompra, reintentos: int = 8) -> Dict:
        """
        Consulta la autorización de una liquidación en el SRI.
        
        Args:
            liquidacion: Instancia de LiquidacionCompra
            reintentos: Número de reintentos si está en procesamiento
            
        Returns:
            Dict con resultado de la autorización
        """
        import time
        
        for intento in range(reintentos):
            try:
                resultado = self.cliente_sri.consultar_autorizacion(liquidacion.clave_acceso)
                
                estado = resultado.get('estado', '')
                
                if estado == 'AUTORIZADO':
                    # Comprobante autorizado
                    liquidacion.estado = 'AUTORIZADA'
                    liquidacion.estado_sri = 'AUTORIZADA'
                    liquidacion.numero_autorizacion = resultado.get('numero_autorizacion')
                    liquidacion.fecha_autorizacion = resultado.get('fecha_autorizacion')
                    liquidacion.xml_autorizado = resultado.get('xml_autorizado')
                    liquidacion.mensaje_sri = 'Comprobante autorizado'
                    liquidacion.save(update_fields=[
                        'estado', 'estado_sri', 'numero_autorizacion', 
                        'fecha_autorizacion', 'xml_autorizado', 'mensaje_sri'
                    ])
                    
                    self._registrar_log(liquidacion, 'AUTORIZADA', 'AUTORIZADA', 
                                       f"Autorización: {liquidacion.numero_autorizacion}")
                    
                    return {
                        'exito': True,
                        'estado': 'AUTORIZADO',
                        'numero_autorizacion': liquidacion.numero_autorizacion,
                        'fecha_autorizacion': liquidacion.fecha_autorizacion,
                        'xml_firmado': liquidacion.xml_firmado,
                        'xml_autorizado': liquidacion.xml_autorizado,
                        'mensajes': ['Comprobante autorizado correctamente']
                    }
                    
                elif estado == 'NO AUTORIZADO':
                    # Comprobante rechazado
                    mensajes = resultado.get('mensajes', [])
                    mensaje_error = self._formatear_mensajes_sri(mensajes)

                    # Caso especial: SRI indica secuencial duplicado (código 45)
                    if self._mensajes_indican_secuencial_registrado(mensajes):
                        numero = f"{liquidacion.serie_formateada}-{liquidacion.secuencia_formateada}"
                        mensaje_error = (
                            "El SRI reporta que el secuencial ya está registrado para esta serie. "
                            f"Número: {numero}. "
                            "Solución: en Configuración → Secuencias, ajuste el 'siguiente secuencial' de "
                            "Liquidación de Compra (03) a un número mayor al último emitido en el SRI para esa serie "
                            "y vuelva a emitir una nueva liquidación."
                        )
                    
                    liquidacion.estado = 'RECHAZADA'
                    liquidacion.estado_sri = 'NO AUTORIZADO'
                    liquidacion.mensaje_sri = mensaje_error
                    liquidacion.save(update_fields=['estado', 'estado_sri', 'mensaje_sri'])
                    
                    self._registrar_log(liquidacion, 'RECHAZADA', 'NO AUTORIZADO', mensaje_error)
                    
                    return {
                        'exito': False,
                        'estado': 'NO AUTORIZADO',
                        'mensajes': mensajes,
                        'xml_firmado': liquidacion.xml_firmado
                    }
                    
                elif estado in ['EN PROCESAMIENTO', 'PENDIENTE'] or self._mensajes_indican_en_procesamiento(resultado.get('mensajes', [])):
                    # Esperar y reintentar
                    if intento < reintentos - 1:
                        logger.info(f"Liquidación {liquidacion.clave_acceso} en procesamiento, reintento {intento + 1}/{reintentos}")
                        time.sleep(3)  # Esperar 3 segundos entre reintentos
                        continue
                    else:
                        # Después de todos los reintentos sigue en procesamiento
                        liquidacion.estado_sri = 'PENDIENTE'
                        liquidacion.mensaje_sri = 'Comprobante en procesamiento en el SRI'
                        liquidacion.save(update_fields=['estado_sri', 'mensaje_sri'])
                        
                        return {
                            'exito': False,
                            'estado': 'PENDIENTE',
                            'mensajes': ['El comprobante sigue en procesamiento. Consulte más tarde.'],
                            'xml_firmado': liquidacion.xml_firmado
                        }
                else:
                    # Estado desconocido
                    return {
                        'exito': False,
                        'estado': 'ERROR',
                        'mensajes': [f'Estado desconocido: {estado}']
                    }
                    
            except Exception as e:
                logger.error(f"Error consultando autorización (intento {intento + 1}): {e}")
                if intento < reintentos - 1:
                    time.sleep(3)
                    continue
                else:
                    return {
                        'exito': False,
                        'estado': 'ERROR',
                        'mensajes': [f'Error al consultar autorización: {str(e)}']
                    }
        
        return {
            'exito': False,
            'estado': 'ERROR',
            'mensajes': ['No se pudo consultar la autorización después de varios intentos']
        }

    def _formatear_mensajes_sri(self, mensajes: list) -> str:
        """
        Formatea los mensajes del SRI para almacenarlos en base de datos.
        
        Args:
            mensajes: Lista de mensajes del SRI
            
        Returns:
            String con mensajes formateados
        """
        if not mensajes:
            return ''
        
        lineas = []
        for msg in mensajes:
            if isinstance(msg, dict):
                identificador = msg.get('identificador', '')
                mensaje = msg.get('mensaje', '')
                tipo = msg.get('tipo', 'INFO')
                lineas.append(f"[{tipo}] {identificador}: {mensaje}")
            else:
                lineas.append(str(msg))
        
        return '\n'.join(lineas)

    def _mensajes_indican_secuencial_registrado(self, mensajes: list) -> bool:
        try:
            for msg in mensajes or []:
                if not isinstance(msg, dict):
                    continue
                identificador = str(msg.get('identificador', '')).strip()
                texto = str(msg.get('mensaje', '')).upper()
                if identificador == '45' or 'SECUENCIAL REGISTRADO' in texto:
                    return True
        except Exception:
            return False
        return False

    def _mensajes_indican_en_procesamiento(self, mensajes: list) -> bool:
        try:
            for msg in mensajes or []:
                if not isinstance(msg, dict):
                    continue
                identificador = str(msg.get('identificador', '')).strip()
                texto = str(msg.get('mensaje', '')).upper()
                if identificador == '70' or 'CLAVE DE ACCESO EN PROCESAMIENTO' in texto:
                    return True
        except Exception:
            return False
        return False

    def _registrar_log(self, liquidacion: LiquidacionCompra, estado: str, 
                      estado_sri: str, mensaje: str) -> None:
        """
        Registra un cambio de estado en el historial de la liquidación.
        
        Args:
            liquidacion: Instancia de LiquidacionCompra
            estado: Nuevo estado interno
            estado_sri: Estado del SRI
            mensaje: Mensaje descriptivo
        """
        try:
            LiquidacionLogCambioEstado.objects.create(
                liquidacion=liquidacion,
                estado=estado,
                estado_sri=estado_sri,
                mensaje=mensaje
            )
        except Exception as e:
            logger.error(f"Error al registrar log de cambio de estado: {e}")

    def reenviar_liquidacion(self, liquidacion: LiquidacionCompra) -> Dict:
        """
        Reenvía una liquidación que fue rechazada o tuvo error.
        
        Args:
            liquidacion: Instancia de LiquidacionCompra
            
        Returns:
            Dict con resultado del reenvío
        """
        if liquidacion.estado not in ['RECHAZADA', 'ERROR']:
            return {
                'exito': False,
                'estado': 'ERROR',
                'mensajes': ['Solo se pueden reenviar liquidaciones rechazadas o con error']
            }
        
        # Cambiar estado a LISTA para poder reprocesar
        liquidacion.estado = 'LISTA'
        liquidacion.save(update_fields=['estado'])
        
        # Procesar nuevamente
        return self.procesar_liquidacion_completa(liquidacion)

    def consultar_estado_actual(self, liquidacion: LiquidacionCompra) -> Dict:
        """
        Consulta el estado actual de una liquidación en el SRI.
        
        Args:
            liquidacion: Instancia de LiquidacionCompra
            
        Returns:
            Dict con estado actual
        """
        if not liquidacion.clave_acceso:
            return {
                'exito': False,
                'estado': 'ERROR',
                'mensajes': ['La liquidación no tiene clave de acceso generada']
            }
        
        return self._consultar_autorizacion(liquidacion, reintentos=1)
