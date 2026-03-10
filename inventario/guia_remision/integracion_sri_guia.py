"""
Integración Django para Guías de Remisión - SRI Ecuador
Completamente independiente de la integración de facturas
"""
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from inventario.models import GuiaRemision, Opciones
from .xml_generator_guia import XMLGeneratorGuiaRemision
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
                clave_nueva = generator.generar_clave_acceso()
                logger.info(f"🔑 Clave generada: {clave_nueva}")
                guia.clave_acceso = clave_nueva
                guia.save()
                logger.info(f"💾 Clave guardada en BD para guía {guia.id}")
            else:
                logger.info(f"✅ Guía ya tiene clave: {guia.clave_acceso}")
            
            # Refrescar del objeto desde BD para asegurar que tiene la clave
            guia.refresh_from_db()
            logger.info(f"🔄 Guía refrescada - Clave actual: {guia.clave_acceso}")
            
            # 2. Generar XML
            xml_sin_firmar = self.generar_xml(guia)
            logger.info(f"📄 XML SIN FIRMAR generado ({len(xml_sin_firmar)} bytes)")

            # 2.1 Validar XML contra XSD (antes de firmar/enviar)
            try:
                xsd_path = Path(settings.BASE_DIR) / 'inventario' / 'guia_remision' / 'GuiaRemision_V1.1.0.xsd'
                generator = XMLGeneratorGuiaRemision(guia, self.empresa, self.opciones)
                resultado_validacion = generator.validar_xml_contra_xsd(xml_sin_firmar, str(xsd_path))
                if not resultado_validacion.get('valido'):
                    errores = (resultado_validacion.get('errores') or '').strip()
                    logger.error(f"❌ XML de guía NO válido según XSD: {resultado_validacion.get('mensaje')}\n{errores}")
                    # Guardar debug local para inspección
                    try:
                        debug_dir = Path(settings.BASE_DIR) / 'media' / 'guias_xml_debug' / str(self.empresa.id)
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        debug_path = debug_dir / f'guia_{guia.numero_completo.replace("-", "_")}_sin_firmar_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xml'
                        debug_path.write_text(xml_sin_firmar, encoding='utf-8')
                        logger.info(f"🧪 XML debug guardado en: {debug_path}")
                    except Exception as e:
                        logger.warning(f"No se pudo guardar XML debug: {e}")

                    # Mensaje corto para UI: tomar la primera línea real tipo "Línea X: ..."
                    primer_error = ''
                    if errores:
                        for linea in errores.split('\n'):
                            if linea.strip().lower().startswith('línea') or linea.strip().lower().startswith('linea'):
                                primer_error = linea.strip()
                                break
                        if not primer_error:
                            primer_error = errores.split('\n', 1)[0].strip()
                    return {
                        'success': False,
                        'message': f"XML inválido según XSD (antes de enviar al SRI). {primer_error or 'Revise estructura del XML.'}",
                        'detalle': resultado_validacion,
                    }
            except Exception as e:
                logger.error(f"No se pudo validar XML contra XSD (se detiene): {e}")
                return {
                    'success': False,
                    'message': f"No se pudo validar el XML localmente contra XSD: {str(e)}",
                }
            
            # DEBUG: Guardar XML sin firmar para inspección
            import re
            clave_en_xml = re.search(r'<claveAcceso>(.*?)</claveAcceso>', xml_sin_firmar)
            if clave_en_xml:
                logger.info(f"🔍 Clave encontrada en XML sin firmar: {clave_en_xml.group(1)}")
            else:
                logger.error(f"❌ NO SE ENCONTRÓ tag <claveAcceso> en el XML sin firmar!")
                logger.error(f"Primeros 1000 caracteres del XML:\n{xml_sin_firmar[:1000]}")
            
            # 3. Firmar XML
            xml_firmado = self.firmar_xml(xml_sin_firmar)
            logger.info(f"🔏 XML FIRMADO generado ({len(xml_firmado)} bytes)")

            # 3.1 Validar XML firmado contra XSD (muchos errores 35 vienen de aquí)
            try:
                xsd_path = Path(settings.BASE_DIR) / 'inventario' / 'guia_remision' / 'GuiaRemision_V1.1.0.xsd'
                generator = XMLGeneratorGuiaRemision(guia, self.empresa, self.opciones)
                resultado_validacion_firmado = generator.validar_xml_contra_xsd(xml_firmado, str(xsd_path))
                if not resultado_validacion_firmado.get('valido'):
                    errores = (resultado_validacion_firmado.get('errores') or '').strip()
                    logger.error(f"❌ XML FIRMADO de guía NO válido según XSD: {resultado_validacion_firmado.get('mensaje')}\n{errores}")
                    try:
                        debug_dir = Path(settings.BASE_DIR) / 'media' / 'guias_xml_debug' / str(self.empresa.id)
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        debug_path = debug_dir / f'guia_{guia.numero_completo.replace("-", "_")}_firmado_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xml'
                        debug_path.write_text(xml_firmado, encoding='utf-8')
                        logger.info(f"🧪 XML firmado debug guardado en: {debug_path}")
                    except Exception as e:
                        logger.warning(f"No se pudo guardar XML firmado debug: {e}")

                    primer_error = ''
                    if errores:
                        for linea in errores.split('\n'):
                            if linea.strip().lower().startswith('línea') or linea.strip().lower().startswith('linea'):
                                primer_error = linea.strip()
                                break
                        if not primer_error:
                            primer_error = errores.split('\n', 1)[0].strip()
                    return {
                        'success': False,
                        'message': f"XML firmado inválido según XSD (antes de enviar al SRI). {primer_error or 'Revise firma/estructura.'}",
                        'detalle': resultado_validacion_firmado,
                    }
            except Exception as e:
                logger.error(f"No se pudo validar XML firmado contra XSD (se detiene): {e}")
                return {
                    'success': False,
                    'message': f"No se pudo validar el XML firmado localmente contra XSD: {str(e)}",
                }
            
            # DEBUG: Verificar clave en XML firmado
            clave_en_xml_firmado = re.search(r'<claveAcceso>(.*?)</claveAcceso>', xml_firmado)
            if clave_en_xml_firmado:
                logger.info(f"🔍✅ Clave EN XML FIRMADO: {clave_en_xml_firmado.group(1)}")
            else:
                logger.error(f"❌❌ NO SE ENCONTRÓ tag <claveAcceso> en el XML FIRMADO!")
                logger.error(f"⚠️ LA FIRMA ELIMINÓ EL TAG - verificar firmador_guia.py")
                logger.error(f"Primeros 1000 caracteres del XML FIRMADO:\n{xml_firmado[:1000]}")
            
            # 4. Guardar XML firmado
            self._guardar_xml(guia, xml_firmado)
            
            # 5. Enviar al SRI
            resultado_envio = self.enviar_guia_sri(guia, xml_firmado)
            
            # IMPORTANTE: Si está DEVUELTA, revisar los mensajes del envío
            if resultado_envio.get('estado') == 'DEVUELTA':
                mensajes_devuelta = resultado_envio.get('mensajes', [])
                errores = []
                for msg in mensajes_devuelta:
                    if isinstance(msg, dict):
                        errores.append(f"{msg.get('identificador', '')}: {msg.get('mensaje', '')}")
                    else:
                        errores.append(str(msg))
                
                mensaje_error = '; '.join(errores) if errores else 'Comprobante devuelto sin detalles'
                logger.error(f"❌ Guía DEVUELTA en recepción: {mensaje_error}")
                
                return {
                    'success': False,
                    'estado': 'DEVUELTA',
                    'message': f"Guía DEVUELTA por el SRI (errores en el XML): {mensaje_error}",
                    'detalle': resultado_envio
                }
            
            # Verificar si el envío fue RECIBIDA (sin errores)
            if resultado_envio.get('estado') == 'RECIBIDA':
                logger.info(f"✅ Guía RECIBIDA por SRI, esperando autorización...")
                
                # 6. Consultar autorización con reintentos (el SRI tarda en procesar)
                max_intentos = 5
                tiempo_espera = 3  # segundos entre intentos
                
                for intento in range(1, max_intentos + 1):
                    logger.info(f"🔄 Intento {intento}/{max_intentos} - Consultando autorización...")
                    
                    resultado_autorizacion = self.consultar_autorizacion(guia)
                    estado = resultado_autorizacion.get('estado')
                    estado_norm = (estado or '').strip().upper().replace(' ', '_')
                    
                    logger.info(f"📋 Estado de autorización: {estado}")
                    
                    # LOG DETALLADO: Ver qué devuelve el SRI
                    logger.info(f"📦 Resultado completo de autorización:")
                    logger.info(f"   - Estado: {estado}")
                    logger.info(f"   - Autorizaciones: {resultado_autorizacion.get('autorizaciones', [])}")
                    logger.info(f"   - Mensajes: {resultado_autorizacion.get('mensajes', [])}")
                    
                    # Si hay autorizaciones, mostrar detalles
                    autorizaciones = resultado_autorizacion.get('autorizaciones', [])
                    if autorizaciones:
                        for idx, aut in enumerate(autorizaciones):
                            logger.info(f"   📄 Autorización {idx+1}:")
                            logger.info(f"      - Estado: {aut.get('estado')}")
                            logger.info(f"      - Número: {aut.get('numeroAutorizacion')}")
                            logger.info(f"      - Fecha: {aut.get('fechaAutorizacion')}")
                            if aut.get('mensajes'):
                                logger.info(f"      - Mensajes en autorización:")
                                for msg in aut.get('mensajes', []):
                                    logger.info(f"         * {msg.get('identificador')}: {msg.get('mensaje')}")
                    
                    if estado_norm in ('AUTORIZADO', 'AUTORIZADA'):
                        # Extraer número de autorización
                        numero_autorizacion = None
                        autorizaciones = resultado_autorizacion.get('autorizaciones', [])
                        if autorizaciones and len(autorizaciones) > 0:
                            numero_autorizacion = autorizaciones[0].get('numeroAutorizacion')
                        
                        guia.estado = 'autorizada'
                        guia.numero_autorizacion = numero_autorizacion or guia.clave_acceso
                        guia.fecha_autorizacion = datetime.now()
                        guia.save()
                        
                        logger.info(f"🎉 Guía AUTORIZADA exitosamente")
                        logger.info(f"   📋 Número de autorización: {guia.numero_autorizacion}")
                        logger.info(f"   📅 Fecha: {guia.fecha_autorizacion}")
                        
                        return {
                            'success': True,
                            'estado': 'AUTORIZADA',
                            'message': 'Guía de remisión procesada y autorizada exitosamente',
                            'clave_acceso': guia.clave_acceso,
                            'numero_autorizacion': guia.numero_autorizacion
                        }
                    
                    elif estado_norm in ('NO_AUTORIZADO', 'NO_AUTORIZADA', 'RECHAZADO', 'RECHAZADA', 'DEVUELTA', 'ERROR'):
                        # Error definitivo, no reintentar
                        logger.error(f"❌ Guía NO AUTORIZADA - Estado: {estado}")
                        
                        mensajes = resultado_autorizacion.get('mensajes', [])
                        errores = []
                        
                        logger.error(f"📋 DETALLES DEL RECHAZO:")
                        logger.error(f"   Total de mensajes: {len(mensajes)}")
                        
                        for idx, msg in enumerate(mensajes):
                            if isinstance(msg, dict):
                                identificador = msg.get('identificador', 'SIN_ID')
                                mensaje_texto = msg.get('mensaje', 'Sin mensaje')
                                tipo = msg.get('tipo', 'DESCONOCIDO')
                                info_adicional = msg.get('informacionAdicional', '')
                                
                                logger.error(f"   Mensaje {idx+1}:")
                                logger.error(f"      - ID: {identificador}")
                                logger.error(f"      - Tipo: {tipo}")
                                logger.error(f"      - Mensaje: {mensaje_texto}")
                                if info_adicional:
                                    logger.error(f"      - Info Adicional: {info_adicional}")
                                
                                errores.append(f"[{identificador}] {mensaje_texto}")
                            else:
                                logger.error(f"   Mensaje {idx+1}: {str(msg)}")
                                errores.append(str(msg))
                        
                        mensaje_error = '; '.join(errores) if errores else resultado_autorizacion.get('mensaje', 'Sin mensaje de error')
                        
                        logger.error(f"❌ RESUMEN ERROR: {mensaje_error}")
                        
                        return {
                            'success': False,
                            'estado': estado_norm or 'NO_AUTORIZADA',
                            'message': f"Guía no autorizada por el SRI: {mensaje_error}",
                            'detalle': resultado_autorizacion
                        }
                    
                    else:
                        # PENDIENTE u otro estado temporal - esperar y reintentar
                        if intento < max_intentos:
                            logger.info(f"⏳ Estado PENDIENTE - Esperando {tiempo_espera}s antes de reintentar...")
                            time.sleep(tiempo_espera)
                        else:
                            logger.warning(f"⚠️ Alcanzado máximo de intentos - Estado: {estado}")
                            return {
                                'success': False,
                                'estado': 'RECIBIDA',
                                'message': f"La guía fue recibida pero aún no está autorizada. Estado: {estado}. Consulte manualmente en unos minutos.",
                                'detalle': resultado_autorizacion
                            }
            
            # Si el envío falló, devolver el error
            return {
                'success': False,
                'estado': resultado_envio.get('estado'),
                'message': f"Error al enviar al SRI: {resultado_envio.get('estado')}",
                'detalle': resultado_envio
            }
            
        except GuiaRemision.DoesNotExist:
            logger.error(f"Guía de remisión {guia_id} no encontrada")
            return {
                'success': False,
                'estado': 'NO_ENCONTRADA',
                'message': f'Guía de remisión {guia_id} no encontrada'
            }
        except Exception as e:
            logger.error(f"Error procesando guía de remisión: {e}")
            return {
                'success': False,
                'estado': 'ERROR',
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
            # Obtener el certificado de firma
            if not self.opciones.firma_electronica:
                raise ValueError("No hay firma electrónica configurada")
            
            logger.info(f"🔏 Iniciando firma de guía de remisión con firmador SRI Ecuador simplificado")
            
            # Leer el contenido del archivo P12
            try:
                with self.opciones.firma_electronica.open('rb') as f:
                    p12_content = f.read()
                logger.info(f"✅ Firma electrónica leída: {len(p12_content)} bytes")
            except Exception as e:
                logger.error(f"❌ Error leyendo firma electrónica: {e}")
                raise ValueError(f"No se pudo leer el certificado de firma: {str(e)}")
            
            password = self.opciones.password_firma
            
            # Usar firmador XAdES-BES simplificado sin elementos Certum
            from inventario.sri.firmador_xades_sri_simple import FirmadorXAdESSRIEcuador
            
            firmador = FirmadorXAdESSRIEcuador(p12_content, password)
            xml_firmado = firmador.firmar_xml(xml_string)
            
            logger.info("✅ XML de guía de remisión firmado exitosamente con XAdES-BES SRI Ecuador")
            return xml_firmado
            
        except Exception as e:
            logger.error(f"❌ Error firmando XML de guía de remisión: {e}")
            raise
    
    def enviar_guia_sri(self, guia, xml_firmado):
        """
        Envía la guía de remisión al SRI
        
        Args:
            guia: Instancia de GuiaRemision
            xml_firmado (str): XML firmado
            
        Returns:
            dict: Resultado del envío (con 'estado')
        """
        try:
            # Crear cliente SRI con el ambiente de Opciones
            tipo_ambiente = self.opciones.tipo_ambiente
            ambiente = 'produccion' if tipo_ambiente == '2' else 'pruebas'
            logger.info(f"🌐 Iniciando envío al SRI - Ambiente: {tipo_ambiente} ({'PRUEBAS' if tipo_ambiente == '1' else 'PRODUCCIÓN'})")
            logger.info(f"📋 Clave de acceso: {guia.clave_acceso}")
            
            cliente = SRIClient(ambiente=ambiente)
            
            # Enviar comprobante con la clave de acceso
            resultado = cliente.enviar_comprobante(xml_firmado, guia.clave_acceso)
            
            logger.info(f"✅ Guía {guia.numero_completo} enviada al SRI - Estado: {resultado.get('estado')}")
            return resultado
            
        except Exception as e:
            logger.error(f"Error enviando guía al SRI: {e}")
            return {
                'estado': 'ERROR',
                'mensajes': [{
                    'identificador': 'CLIENT_ERROR',
                    'mensaje': str(e),
                    'tipo': 'ERROR'
                }]
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
            
            # Crear cliente SRI con el ambiente de Opciones
            tipo_ambiente = self.opciones.tipo_ambiente
            ambiente = 'produccion' if tipo_ambiente == '2' else 'pruebas'
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
        Guarda el XML firmado en el storage LOCAL (evita S3 403)
        
        Args:
            guia: Instancia de GuiaRemision
            xml_content (str): Contenido del XML
        """
        try:
            # GUARDADO LOCAL - evitar S3 por permisos
            base_dir = Path(settings.BASE_DIR) / 'media' / 'guias_xml' / str(self.empresa.id)
            base_dir.mkdir(parents=True, exist_ok=True)
            
            nombre_archivo = f'guia_{guia.numero_completo.replace("-", "_")}.xml'
            ruta_completa = base_dir / nombre_archivo
            
            # Guardar archivo localmente
            ruta_completa.write_text(xml_content, encoding='utf-8')
            
            # Actualizar guía con contenido del XML
            guia.xml_autorizado = xml_content
            guia.save()
            
            logger.info(f"✅ XML guardado localmente en: {ruta_completa}")
            
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
