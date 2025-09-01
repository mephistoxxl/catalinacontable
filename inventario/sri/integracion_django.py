import os
import logging
import random
from datetime import datetime
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
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
        """Inicializa la integración con configuración desde Opciones"""
        # 🔄 SINCRONIZAR con Opciones.tipo_ambiente
        try:
            opciones = Opciones.objects.first()
            if opciones and opciones.tipo_ambiente:
                self.ambiente = 'produccion' if opciones.tipo_ambiente == '2' else 'pruebas'
            else:
                self.ambiente = 'pruebas'
        except Exception:
            self.ambiente = 'pruebas'

        self.cliente = SRIClient(ambiente=self.ambiente)

    def enviar_factura(self, factura_id):
        """Genera, firma y envía la factura al SRI.

        Solo realiza el proceso de recepción del comprobante y
        actualiza el estado de la factura con la respuesta obtenida
        (p.ej. ``RECIBIDA`` o ``DEVUELTA``) sin consultar su
        autorización posterior.

        Args:
            factura_id (int): ID de la factura en la base de datos.

        Returns:
            dict: Resultado del envío al SRI.
        """
        estado_recep = None
        estado_auth = None
        raw_response = None

        try:
            factura = Factura.objects.get(id=factura_id)

            # Si la factura ya está autorizada no se vuelve a enviar
            if hasattr(factura, 'estado_sri') and factura.estado_sri in ('AUTORIZADA', 'AUTORIZADO'):
                return {
                    'success': True,
                    'message': f'La factura ya está {factura.estado_sri} en el SRI',
                    'estado': factura.estado_sri,
                }

            # Verificar que la factura esté en estado correcto
            if hasattr(factura, 'estado') and factura.estado != 'PENDIENTE':
                logger.error(
                    "Factura %s en estado inválido antes de envío - estado_recep=%s, estado_auth=%s, raw_response=%s",
                    factura.id, estado_recep, estado_auth, raw_response
                )
                return {
                    'success': False,
                    'message': f'La factura debe estar en estado PENDIENTE. Estado actual: {factura.estado}'
                }

            # Asegurar que la factura tenga clave de acceso
            if not factura.clave_acceso:
                factura.save()
                if not factura.clave_acceso:
                    raise ValueError(f"No se pudo generar clave de acceso para factura {factura.id}")

            clave_acceso = factura.clave_acceso

            # Generar y firmar XML
            xml_path = self.generar_xml_factura(factura)
            xml_firmado_path = xml_path.replace('.xml', '_firmado.xml')
            success = self._firmar_xml_xades_bes(xml_path, xml_firmado_path)
            if not success:
                raise Exception("Error al firmar XML con XAdES-BES")

            with open(xml_firmado_path, 'r', encoding='utf-8') as f:
                xml_firmado_content = f.read()

            resultado = self.cliente.enviar_comprobante(xml_firmado_content, clave_acceso)

            # Guardar estado de recepción (RECIBIDA/DEVUELTA)
            self._actualizar_factura_con_resultado(factura, resultado, clave_acceso)

            estado_recep = resultado.get('estado', 'ERROR')
            raw_response = resultado.get('raw_response')
            mensajes_recep = resultado.get('mensajes', [])

            if estado_recep != 'RECIBIDA':
                logger.error(
                    "Error en recepción SRI - estado_recep=%s, estado_auth=%s, raw_response=%s",
                    estado_recep, estado_auth, raw_response
                )

            return {
                'success': estado_recep == 'RECIBIDA',
                'message': 'Comprobante enviado correctamente' if estado_recep == 'RECIBIDA' else 'Error en recepción',
                'estado': estado_recep,
                'mensajes': mensajes_recep,
                'resultado': resultado,
            }

        except Factura.DoesNotExist:
            logger.error(
                "Factura %s no encontrada - estado_recep=%s, estado_auth=%s, raw_response=%s",
                factura_id, estado_recep, estado_auth, raw_response
            )
            return {
                'success': False,
                'message': f'No se encontró la factura con ID {factura_id}'
            }
        except Exception as e:
            logger.error(f"Error enviando factura {factura_id}: {e}")
            logger.error(
                "Estados SRI al error - estado_recep=%s, estado_auth=%s, raw_response=%s",
                estado_recep, estado_auth, raw_response
            )
            return {
                'success': False,
                'message': str(e)
            }

    def procesar_factura(self, factura_id):
        """
        Procesa una factura completa: genera XML, firma, envía al SRI y actualiza estado
        
        Args:
            factura_id (int): ID de la factura en la base de datos
            
        Returns:
            dict: Resultado del procesamiento
        """
        estado_recep = None
        estado_auth = None
        raw_response = None

        try:
            # Obtener factura
            factura = Factura.objects.get(id=factura_id)
            
            # 🎯 ESTABLECER ESTADO PENDIENTE AL INICIAR PROCESAMIENTO SRI
            # Solo si no tiene estado SRI previo (estado_sri vacío = factura local)
            if not factura.estado_sri or factura.estado_sri == '':
                factura.estado_sri = 'PENDIENTE'
                factura.save(update_fields=['estado_sri'])
                logger.info(f"Factura {factura.id} cambió estado: LOCAL → PENDIENTE (enviando al SRI)")
            
            # Lógica de idempotencia y control por estados existentes
            # 🔧 FIX CRÍTICO: Reconocer tanto AUTORIZADA como AUTORIZADO
            if hasattr(factura, 'estado_sri') and factura.estado_sri in ('AUTORIZADA', 'AUTORIZADO'):
                return {
                    'success': True,
                    'message': f'La factura ya está {factura.estado_sri} en el SRI',
                    'resultado': {'estado': factura.estado_sri}
                }

            # Si fue RECHAZADA, no intentar enviar desde aquí (usar reenvío explícito)
            if hasattr(factura, 'estado_sri') and factura.estado_sri == 'RECHAZADA':
                logger.error(
                    "Factura %s rechazada previamente - estado_recep=%s, estado_auth=%s, raw_response=%s",
                    factura.id, estado_recep, estado_auth, raw_response
                )
                return {
                    'success': False,
                    'message': 'La factura fue RECHAZADA por el SRI. Use la opción de Reenviar para generar un nuevo intento.'
                }

            # Si ya tiene clave_acceso y está RECIBIDA/PENDIENTE, solo consultar autorización sin reenviar
            if getattr(factura, 'clave_acceso', None) and hasattr(factura, 'estado_sri') and factura.estado_sri in ['RECIBIDA', 'PENDIENTE']:
                estado_recep = factura.estado_sri
                resultado_auth = self.cliente.consultar_autorizacion(factura.clave_acceso)
                self._actualizar_factura_con_resultado(factura, resultado_auth, factura.clave_acceso)
                estado_auth = resultado_auth.get('estado')
                raw_response = resultado_auth.get('raw_response')
                # 🔧 FIX CRÍTICO: Reconocer tanto AUTORIZADA como AUTORIZADO en consulta
                if resultado_auth.get('estado') in ('AUTORIZADA', 'AUTORIZADO'):
                    self._generar_ride_autorizado(factura, resultado_auth)
                    return {
                        'success': True,
                        'message': 'Factura autorizada exitosamente',
                        'resultado': resultado_auth
                    }
                else:
                    logger.error(
                        "Autorización pendiente o rechazada - estado_recep=%s, estado_auth=%s, raw_response=%s",
                        estado_recep, estado_auth, raw_response
                    )
                    return {
                        'success': False,
                        'message': 'La factura aún no está autorizada. Intente consultar nuevamente en unos minutos.',
                        'resultado': resultado_auth
                    }

            # Verificar que la factura esté en estado adecuado (interno)
            if hasattr(factura, 'estado') and factura.estado != 'PENDIENTE':
                logger.error(
                    "Factura %s en estado interno inválido - estado_recep=%s, estado_auth=%s, raw_response=%s",
                    factura.id, estado_recep, estado_auth, raw_response
                )
                return {
                    'success': False,
                    'message': f'La factura debe estar en estado PENDIENTE. Estado actual: {factura.estado}'
                }
            
            # 🔧 FIX CRÍTICO: NUNCA regenerar clave de acceso - usar siempre la existente
            # La clave debe haberse generado al crear/guardar la factura
            if not factura.clave_acceso:
                # Si no tiene clave, forzar guardar para que se genere automáticamente
                logger.warning(f"Factura {factura.id} sin clave de acceso. Forzando generación...")
                factura.save()  # Esto disparará la generación automática en el modelo
                
                # Verificar que se generó correctamente
                if not factura.clave_acceso:
                    raise ValueError(f"No se pudo generar clave de acceso para factura {factura.id}")
                    
                logger.info(f"Clave de acceso generada automáticamente: {factura.clave_acceso}")
            else:
                logger.info(f"Usando clave de acceso existente: {factura.clave_acceso}")
            
            # IMPORTANTE: Usar SIEMPRE la clave de la factura (ya persistida)
            clave_acceso = factura.clave_acceso
            
            # Generar XML (ahora la factura ya tiene clave_acceso)
            # ✅ XML se valida automáticamente contra XSD en generar_xml_factura
            xml_path = self.generar_xml_factura(factura)
            
            # 🎯 FIRMAR XML CON XAdES-BES (requerimiento SRI)
            xml_firmado_path = xml_path.replace('.xml', '_firmado.xml')
            success = self._firmar_xml_xades_bes(xml_path, xml_firmado_path)
            if not success:
                raise Exception("Error al firmar XML con XAdES-BES")
            
            # Enviar al SRI (usando la clave ya persistida)
            with open(xml_firmado_path, 'r', encoding='utf-8') as f:
                xml_firmado_content = f.read()
            
            resultado = self.cliente.enviar_comprobante(xml_firmado_content, clave_acceso)

            # Actualizar factura con resultado (sin cambiar la clave de acceso)
            self._actualizar_factura_con_resultado(factura, resultado, clave_acceso)

            estado_recep = resultado.get('estado', 'ERROR')
            raw_response = resultado.get('raw_response')

            # Si fue recibido, solicitar autorización
            if estado_recep == 'RECIBIDA':
                resultado_auth = self.cliente.consultar_autorizacion(clave_acceso)

                # 🔧 FIX: SIEMPRE actualizar el estado tras consultar autorización
                self._actualizar_factura_con_resultado(factura, resultado_auth, clave_acceso)

                estado_auth = resultado_auth.get('estado', '').upper()
                raw_response = resultado_auth.get('raw_response')
                if estado_auth in ('AUTORIZADA', 'AUTORIZADO'):
                    # Generar RIDE autorizado
                    self._generar_ride_autorizado(factura, resultado_auth)

                    return {
                        'success': True,
                        'message': 'Factura autorizada exitosamente',
                        'resultado': resultado_auth
                    }
                elif estado_auth == 'PENDIENTE':
                    # Estado pendiente - no es un error, solo necesita más tiempo
                    mensajes_auth = resultado_auth.get('mensajes', [])
                    mensaje_detalle = mensajes_auth[0].get('mensaje', 'El comprobante está pendiente de autorización') if mensajes_auth else 'El comprobante está pendiente de autorización'
                    logger.error(
                        "Autorización pendiente - estado_recep=%s, estado_auth=%s, raw_response=%s",
                        estado_recep, estado_auth, raw_response
                    )
                    return {
                        'success': False,
                        'message': f"Pendiente de autorización: {mensaje_detalle}. Intente nuevamente en unos minutos.",
                        'estado': 'PENDIENTE',
                        'resultado': resultado_auth
                    }
                else:
                    # Otros estados (NO_AUTORIZADA, ERROR, etc.)
                    mensajes_auth = resultado_auth.get('mensajes', [])
                    mensaje_detalle = mensajes_auth[0].get('mensaje', 'Error desconocido') if mensajes_auth else 'Error desconocido'
                    logger.error(
                        "Error en autorización - estado_recep=%s, estado_auth=%s, raw_response=%s",
                        estado_recep, estado_auth, raw_response
                    )
                    return {
                        'success': False,
                        'message': f"Error en autorización: {mensaje_detalle}",
                        'resultado': resultado_auth
                    }
            else:
                # El comprobante no fue recibido correctamente
                mensajes_recep = resultado.get('mensajes', [])
                mensaje_detalle = mensajes_recep[0].get('mensaje', 'Error desconocido') if mensajes_recep else 'Error desconocido'

                if estado_recep == 'PENDIENTE':
                    message = f"Recepción pendiente: {mensaje_detalle}. Intente nuevamente en unos minutos."
                else:
                    message = f"Error en recepción: {mensaje_detalle}"

                logger.error(
                    "Error en recepción - estado_recep=%s, estado_auth=%s, raw_response=%s",
                    estado_recep, estado_auth, raw_response
                )

                return {
                    'success': False,
                    'message': message,
                    'estado': estado_recep,
                    'resultado': resultado
                }
                
        except Factura.DoesNotExist:
            logger.error(
                "Factura %s no encontrada - estado_recep=%s, estado_auth=%s, raw_response=%s",
                factura_id, estado_recep, estado_auth, raw_response
            )
            return {
                'success': False,
                'message': f'No se encontró la factura con ID {factura_id}'
            }
        except Exception as e:
            logger.error(f"Error procesando factura {factura_id}: {str(e)}")
            logger.error(
                "Estados SRI al error - estado_recep=%s, estado_auth=%s, raw_response=%s",
                estado_recep, estado_auth, raw_response
            )
            return {
                'success': False,
                'message': f'Error interno: {str(e)}'
            }
    
    def generar_xml_factura(self, factura, validar_xsd=True):
        """
        Genera el XML de una factura y lo guarda en el sistema de archivos
        
        Args:
            factura: Instancia de Factura
            validar_xsd: Si debe validar contra XSD (por defecto True)
            
        Returns:
            str: Ruta del archivo XML generado
        """
        try:
            # Asegurarse de que existan formas de pago antes de generar
            if not factura.formas_pago.exists():
                raise ValueError(
                    f"Factura {factura.id} no tiene formas de pago registradas"
                )

            # Generar XML
            xml_generator = SRIXMLGenerator()
            xml_content = xml_generator.generar_xml_factura(factura)
            
            # Crear nombre de archivo único
            xml_filename = f"factura_{factura.numero}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xml"
            xml_path = os.path.join(settings.MEDIA_ROOT, "facturas_xml", xml_filename)
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(xml_path), exist_ok=True)
            
            # 🔧 FIX: Validar XML contra XSD OBLIGATORIAMENTE
            if validar_xsd:
                xsd_path = self._obtener_ruta_xsd()
                resultado_validacion = xml_generator.validar_xml_contra_xsd(xml_content, xsd_path)
                
                if not resultado_validacion['valido']:
                    # 🚨 CRÍTICO: XML inválido debe detener todo el proceso
                    errores_detalle = resultado_validacion.get('errores', 'Sin detalles de error')
                    error_msg = f"XML generado NO VÁLIDO según XSD del SRI: {resultado_validacion['mensaje']}\nDetalles: {errores_detalle}"
                    logger.error(f"❌ {error_msg}")
                    
                    # Guardar XML problemático para debugging
                    debug_filename = f"factura_{factura.numero}_INVALID_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
                    debug_path = os.path.join(settings.MEDIA_ROOT, "facturas_xml", "debug", debug_filename)
                    os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                    
                    with open(debug_path, 'w', encoding='utf-8') as f:
                        f.write(xml_content)
                    
                    logger.error(f"📁 XML inválido guardado para debugging en: {debug_path}")
                    
                    # 🛑 FALLAR COMPLETAMENTE - No continuar con XML inválido
                    raise Exception(f"Validación XSD FALLÓ: {error_msg}. XML debug guardado en: {debug_path}")
                else:
                    logger.info("✅ XML generado válido según XSD")
            
            # Guardar XML
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            logger.info(f"XML generado en: {xml_path}")
            return xml_path
            
        except Exception as e:
            logger.error(f"Error generando XML para factura {factura.numero}: {str(e)}")
            raise Exception(f"Error generando XML: {str(e)}")
    
    def _validar_xml_generado(self, xml_path):
        """
        Valida el XML generado contra el XSD oficial del SRI
        📋 Nota: Este método se mantiene para validaciones independientes,
        pero la validación principal ahora se hace en generar_xml_factura()
        
        Args:
            xml_path: Ruta del archivo XML a validar
            
        Raises:
            Exception: Si el XML no es válido según el XSD
        """
        # Leer el contenido del XML
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Obtener la ruta del XSD
        xsd_path = self._obtener_ruta_xsd()
        
        # Crear generador para usar el método de validación
        xml_generator = SRIXMLGenerator()
        
        # Validar contra el XSD
        logger.info(f"🔍 Validando XML independiente contra XSD: {xsd_path}")
        resultado_validacion = xml_generator.validar_xml_contra_xsd(xml_content, xsd_path)
        
        if not resultado_validacion['valido']:
            errores_detalle = resultado_validacion.get('errores', 'Sin detalles de error')
            logger.error(f"❌ Error de validación XSD independiente: {resultado_validacion['mensaje']}\nDetalles: {errores_detalle}")
            
            # Guardar XML problemático para debugging
            debug_path = xml_path.replace('.xml', '_INVALID_VALIDATION.xml')
            import shutil
            shutil.copy(xml_path, debug_path)
            logger.error(f"📁 XML inválido guardado para debugging en: {debug_path}")
            
            # 🛑 FALLAR COMPLETAMENTE
            raise Exception(f"XML NO VÁLIDO según XSD del SRI: {resultado_validacion['mensaje']}. Detalles: {errores_detalle}. Debug: {debug_path}")
        else:
            logger.info("✅ XML válido según XSD del SRI")
    
    def _obtener_ruta_xsd(self):
        """
        Obtiene la ruta del archivo XSD correspondiente
        
        Returns:
            str: Ruta del archivo XSD
        """
        import os
        
        # XSD para facturas (código 01)
        xsd_filename = 'factura_V1.1.0.xsd'
        
        # Buscar XSD en el directorio del módulo SRI
        sri_dir = os.path.dirname(__file__)
        xsd_path = os.path.join(sri_dir, xsd_filename)
        
        if not os.path.exists(xsd_path):
            # Buscar en subdirectorio xsd
            xsd_path = os.path.join(sri_dir, 'xsd', xsd_filename)
            
        if not os.path.exists(xsd_path):
            # Buscar en directorio padre
            parent_dir = os.path.dirname(sri_dir)
            xsd_path = os.path.join(parent_dir, 'xsd', xsd_filename)
            
        if not os.path.exists(xsd_path):
            raise FileNotFoundError(f"No se encontró el archivo XSD: {xsd_filename}")
        
        return xsd_path
    
    def _generar_clave_acceso(self, factura):
        """
        Genera la clave de acceso según especificaciones del SRI
        
        Args:
            factura: Instancia de Factura
            
        Returns:
            str: Clave de acceso generada
            
        Raises:
            ValueError: Si la factura ya tiene clave de acceso (evitar regeneración)
        """
        # 🔧 FIX: Evitar regenerar si ya existe
        if factura.clave_acceso:
            logger.warning(f"Factura {factura.id} ya tiene clave de acceso: {factura.clave_acceso}")
            return factura.clave_acceso
        
        # Formato: [fecha(8)][tipo_comprobante(2)][ruc(13)][ambiente(1)][serie(6)][numero_secuencial(9)][codigo_numerico(8)][tipo_emision(1)][digito_verificador(1)]
        
        fecha = (factura.fecha_emision or datetime.now()).strftime('%d%m%Y')
        tipo_comprobante = '01'  # Factura
        
        # Obtener RUC desde configuración
        opciones = Opciones.objects.first()
        if not opciones or not opciones.identificacion:
            raise ValueError("RUC no configurado en Opciones")
        ruc = opciones.identificacion.zfill(13)
        
        # 🔄 SINCRONIZAR con Opciones.tipo_ambiente
        try:
            opciones = Opciones.objects.first()
            if opciones and opciones.tipo_ambiente in ['1', '2']:
                ambiente = opciones.tipo_ambiente
            else:
                ambiente = '1'
        except Exception:
            ambiente = '1'
        serie = f"{factura.establecimiento}{factura.punto_emision}"
        
        # Usar el campo correcto para la secuencia
        if hasattr(factura, 'secuencia'):
            secuencial = str(factura.secuencia).zfill(9)
        elif hasattr(factura, 'numero_factura'):
            secuencial = str(factura.numero_factura).zfill(9)
        else:
            secuencial = str(factura.id).zfill(9)
            
        codigo_numerico = f"{random.randint(0, 99999999):08d}"  # Código aleatorio
        tipo_emision = '1'  # Normal
        
        clave_base = f"{fecha}{tipo_comprobante}{ruc}{ambiente}{serie}{secuencial}{codigo_numerico}{tipo_emision}"
        digito_verificador = self._calcular_digito_verificador(clave_base)
        
        clave_completa = clave_base + digito_verificador
        logger.info(f"Clave de acceso generada para factura {factura.id}: {clave_completa}")
        return clave_completa
    
    def _calcular_digito_verificador(self, clave):
        """
        Calcula el dígito verificador para la clave de acceso según algoritmo SRI
        Usa coeficientes [2,3,4,5,6,7] aplicados de derecha a izquierda, repitiendo
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
            clave_acceso: Clave de acceso (solo para verificación, no para sobrescribir)
        """
        # 🔧 FIX: Solo actualizar clave_acceso si no existe (evitar sobrescribir)
        if not factura.clave_acceso:
            factura.clave_acceso = clave_acceso
            logger.warning(f"Clave de acceso asignada tardíamente a factura {factura.id}: {clave_acceso}")
        elif factura.clave_acceso != clave_acceso:
            logger.error(f"INCONSISTENCIA: Factura {factura.id} tiene clave {factura.clave_acceso} pero se intentó usar {clave_acceso}")
            # Usar la clave que ya está en la factura para mantener consistencia
            clave_acceso = factura.clave_acceso
        
        estado = resultado.get('estado', 'ERROR')
        # 🔧 FIX: Normalizar variantes de estado que puede devolver el SRI
        estado_normalizado = estado.upper().replace(' ', '_') if isinstance(estado, str) else str(estado).upper()
        
        logger.info(f"Actualizando factura {factura.id} con estado SRI: '{estado}' (normalizado: '{estado_normalizado}')")

        # 🔧 FIX: Manejo completo de estados AUTORIZADA/AUTORIZADO
        if estado_normalizado in ('AUTORIZADA', 'AUTORIZADO'):
            if hasattr(factura, 'estado'):
                factura.estado = 'AUTORIZADO'
            if hasattr(factura, 'estado_sri'):
                factura.estado_sri = 'AUTORIZADA'
            if hasattr(factura, 'mensaje_sri'):
                factura.mensaje_sri = 'Comprobante autorizado'
                
            # Obtener datos de autorización
            autorizaciones = resultado.get('autorizaciones', [])
            if autorizaciones:
                aut = autorizaciones[0]
                if hasattr(factura, 'numero_autorizacion'):
                    factura.numero_autorizacion = aut.get('numeroAutorizacion')
                if hasattr(factura, 'fecha_autorizacion'):
                    fecha_str = aut.get('fechaAutorizacion')
                    if fecha_str:
                        try:
                            from datetime import datetime
                            factura.fecha_autorizacion = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
                        except:
                            logger.warning(f"Error parseando fecha autorización: {fecha_str}")
                if hasattr(factura, 'xml_autorizado'):
                    factura.xml_autorizado = aut.get('comprobante') or factura.xml_autorizado
            
            logger.info(f"Factura {factura.id} marcada como AUTORIZADA")

        # 🔧 FIX: Manejo completo de estados de rechazo
        elif estado_normalizado in ('NO_AUTORIZADA', 'RECHAZADA', 'NO_AUTORIZADO', 'DEVUELTA'):
            if hasattr(factura, 'estado'):
                factura.estado = 'RECHAZADO'
            if hasattr(factura, 'estado_sri'):
                factura.estado_sri = 'RECHAZADA'
            if hasattr(factura, 'mensaje_sri'):
                mensajes = resultado.get('mensajes', [])
                mensaje_detalle = mensajes[0].get('mensaje', 'Comprobante rechazado') if mensajes else 'Comprobante rechazado'
                factura.mensaje_sri = f"Rechazado: {mensaje_detalle}"
            
            logger.info(f"Factura {factura.id} marcada como RECHAZADA")

        elif estado_normalizado == 'RECIBIDA':
            if hasattr(factura, 'estado'):
                factura.estado = 'RECIBIDA'
            if hasattr(factura, 'estado_sri'):
                factura.estado_sri = 'RECIBIDA'
            if hasattr(factura, 'mensaje_sri'):
                factura.mensaje_sri = 'Comprobante recibido por el SRI'
            
            logger.info(f"Factura {factura.id} marcada como RECIBIDA")

        elif estado_normalizado == 'PENDIENTE':
            if hasattr(factura, 'estado'):
                factura.estado = 'PENDIENTE'
            if hasattr(factura, 'estado_sri'):
                factura.estado_sri = 'PENDIENTE'
            if hasattr(factura, 'mensaje_sri'):
                mensajes = resultado.get('mensajes', [])
                mensaje_detalle = mensajes[0].get('mensaje', 'Pendiente de autorización') if mensajes else 'Pendiente de autorización'
                factura.mensaje_sri = f"Pendiente: {mensaje_detalle}"
            
            logger.info(f"Factura {factura.id} marcada como PENDIENTE")

        else:  # ERROR y otros estados
            if hasattr(factura, 'estado'):
                factura.estado = 'ERROR'
            if hasattr(factura, 'estado_sri'):
                factura.estado_sri = 'ERROR'
            if hasattr(factura, 'mensaje_sri'):
                mensajes = resultado.get('mensajes', [])
                mensaje_error = mensajes[0].get('mensaje', 'Error desconocido') if mensajes else 'Error desconocido'
                factura.mensaje_sri = f"Error: {mensaje_error}"
            
            logger.warning(f"Factura {factura.id} marcada como ERROR - Estado desconocido: {estado}")
        
        # 🔧 FIX: Guardar mensajes completos si el campo existe
        if hasattr(factura, 'mensaje_sri_detalle'):
            factura.mensaje_sri_detalle = str(resultado.get('mensajes', []))
        
        # 🔧 FIX: SIEMPRE guardar los cambios
        factura.save()
        logger.info(f"Factura {factura.id} actualizada y guardada en BD")
    
    def _firmar_xml_xades_bes(self, xml_path, xml_firmado_path):
        """Firma un XML utilizando el esquema XAdES-BES."""
        try:
            from .firmador_xades import firmar_xml_xades_bes
            firmar_xml_xades_bes(xml_path, xml_firmado_path)
            logger.info("XML firmado exitosamente con XAdES-BES")
            return True
        except Exception as e:
            logger.error(f"Error crítico en proceso de firma: {e}")
            raise Exception(f"PROCESO DE FIRMA FALLÓ COMPLETAMENTE: {e}")
    
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
            # ✅ USAR MÉTODO CORRECTO: generar_ride_factura_firmado
            pdf_path = ride_gen.generar_ride_factura_firmado(factura, firmar=False)
            
            # Leer contenido del PDF generado
            with open(pdf_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            
            # Obtener RUC para organizar archivos
            opciones = Opciones.objects.first()
            ruc = opciones.identificacion if opciones else 'sin_ruc'
            
            # Guardar RIDE
            ride_filename = f"RIDE_{factura.numero}.pdf"
            ride_path = f"rides/{ruc}/{ride_filename}"
            
            ride_file = ContentFile(pdf_content)
            saved_path = default_storage.save(ride_path, ride_file)
            
            # Actualizar factura con ruta del RIDE si el campo existe
            if hasattr(factura, 'ride_autorizado'):
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
        estado_recep = None
        estado_auth = None
        raw_response = None

        try:
            factura = Factura.objects.get(id=factura_id)
            
            if not factura.clave_acceso:
                logger.error(
                    "Consulta de estado sin clave - estado_recep=%s, estado_auth=%s, raw_response=%s",
                    estado_recep, estado_auth, raw_response
                )
                return {
                    'success': False,
                    'message': 'La factura no tiene clave de acceso'
                }
            
            resultado = self.cliente.consultar_autorizacion(factura.clave_acceso)
            estado_auth = resultado.get('estado', '').upper()
            raw_response = resultado.get('raw_response')
            
            # 🔧 FIX: Actualizar estado SIEMPRE tras consultar
            self._actualizar_factura_con_resultado(factura, resultado, factura.clave_acceso)
            
            # 🔧 FIX: Crear respuesta más informativa con mejor manejo de estados
            estado = resultado.get('estado', 'ERROR').upper()
            if estado in ('AUTORIZADA', 'AUTORIZADO'):
                # 🔧 FIX: Generar RIDE si está autorizada
                if hasattr(self, '_generar_ride_autorizado'):
                    try:
                        self._generar_ride_autorizado(factura, resultado)
                    except Exception as e:
                        logger.warning(f"Error generando RIDE para factura {factura.id}: {e}")
                
                message = 'Factura autorizada exitosamente'
                success = True
            elif estado == 'PENDIENTE':
                message = 'La factura aún está pendiente de autorización. Intente nuevamente en unos minutos.'
                success = False
            elif estado in ('NO_AUTORIZADA', 'RECHAZADA', 'NO_AUTORIZADO', 'DEVUELTA'):
                message = 'La factura fue rechazada por el SRI'
                success = False
            else:
                mensajes = resultado.get('mensajes', [])
                mensaje_detalle = mensajes[0].get('mensaje', 'Error desconocido') if mensajes else 'Error desconocido'
                message = f'Error en la consulta: {mensaje_detalle}'
                success = False
            
            if not success:
                logger.error(
                    "Consulta estado SRI fallo - estado_recep=%s, estado_auth=%s, raw_response=%s",
                    estado_recep, estado_auth, raw_response
                )

            return {
                'success': success,
                'message': message,
                'estado': estado,
                'resultado': resultado
            }
            
        except Factura.DoesNotExist:
            logger.error(
                "Factura %s no encontrada al consultar estado - estado_recep=%s, estado_auth=%s, raw_response=%s",
                factura_id, estado_recep, estado_auth, raw_response
            )
            return {
                'success': False,
                'message': f'Factura con ID {factura_id} no encontrada'
            }
        except Exception as e:
            logger.error(
                "Error consultando estado de factura %s: %s", factura_id, e
            )
            logger.error(
                "Estados SRI al error - estado_recep=%s, estado_auth=%s, raw_response=%s",
                estado_recep, estado_auth, raw_response
            )
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
        estado_recep = None
        estado_auth = None
        raw_response = None

        try:
            factura = Factura.objects.get(id=factura_id)
            
            # Verificar que pueda ser reenviada
            if hasattr(factura, 'estado') and factura.estado not in ['RECHAZADO', 'ERROR']:
                logger.error(
                    "Reenvío no permitido - estado_recep=%s, estado_auth=%s, raw_response=%s",
                    estado_recep, estado_auth, raw_response
                )
                return {
                    'success': False,
                    'message': f'Solo se pueden reenviar facturas rechazadas o con error. Estado actual: {factura.estado}'
                }
            
            # Resetear estado
            if hasattr(factura, 'estado'):
                factura.estado = 'PENDIENTE'
            if hasattr(factura, 'estado_sri'):
                factura.estado_sri = 'PENDIENTE'
            factura.clave_acceso = None
            if hasattr(factura, 'numero_autorizacion'):
                factura.numero_autorizacion = None
            if hasattr(factura, 'fecha_autorizacion'):
                factura.fecha_autorizacion = None
            if hasattr(factura, 'mensaje_sri'):
                factura.mensaje_sri = None
            if hasattr(factura, 'mensaje_sri_detalle'):
                factura.mensaje_sri_detalle = None
            factura.save()
            
            # Procesar nuevamente
            return self.procesar_factura(factura_id)
            
        except Factura.DoesNotExist:
            logger.error(
                "Factura %s no encontrada para reenvío - estado_recep=%s, estado_auth=%s, raw_response=%s",
                factura_id, estado_recep, estado_auth, raw_response
            )
            return {
                'success': False,
                'message': f'Factura con ID {factura_id} no encontrada'
            }
        except Exception as e:
            logger.error(f"Error reenviando factura {factura_id}: {e}")
            logger.error(
                "Estados SRI al error - estado_recep=%s, estado_auth=%s, raw_response=%s",
                estado_recep, estado_auth, raw_response
            )
            return {
                'success': False,
                'message': str(e)
            }

    def _es_estado_autorizado(self, estado):
        """
        🔍 Verifica si un estado indica que la factura está autorizada
        
        Args:
            estado (str): Estado a verificar
            
        Returns:
            bool: True si el estado indica autorización
        """
        if not estado:
            return False
            
        # Normalizar a mayúsculas para comparación
        estado_upper = str(estado).upper().strip()
        
        # Estados que indican autorización
        estados_autorizados = {
            'AUTORIZADA',
            'AUTORIZADO'
        }
        
        return estado_upper in estados_autorizados


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
    facturas_pendientes = Factura.objects.all()
    
    # Filtrar por estado si el campo existe
    if hasattr(Factura, 'estado'):
        facturas_pendientes = facturas_pendientes.filter(estado__in=['RECIBIDA', 'PENDIENTE'])
    
    integration = SRIIntegration()
    
    resultados = []
    for factura in facturas_pendientes:
        if factura.clave_acceso:  # Solo consultar facturas que ya tienen clave
            resultado = integration.consultar_estado_factura(factura.id)
            resultados.append({
                'factura_id': factura.id,
                'numero': factura.numero,
                'resultado': resultado
            })
    
    return resultados


def validar_xml_existente(xml_path):
    """
    Valida un archivo XML existente contra el XSD
    Útil para debugging y pruebas
    
    Args:
        xml_path: Ruta del archivo XML a validar
        
    Returns:
        dict: Resultado de la validación
    """
    try:
        integration = SRIIntegration()
        
        # Leer el XML
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Obtener XSD
        xsd_path = integration._obtener_ruta_xsd()
        
        # Validar
        xml_generator = SRIXMLGenerator()
        xml_generator.validar_xml_contra_xsd(xml_content, xsd_path)
        
        return {
            'success': True,
            'message': 'XML válido según XSD del SRI',
            'xml_path': xml_path,
            'xsd_path': xsd_path
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': str(e),
            'xml_path': xml_path,
            'error': str(e)
        }


def validar_lote_xml_facturas():
    """
    Valida todos los XML de facturas existentes
    Útil para verificar la calidad de XMLs ya generados
    """
    import glob
    
    xml_pattern = os.path.join(settings.MEDIA_ROOT, "facturas_xml", "*.xml")
    xml_files = glob.glob(xml_pattern)
    
    resultados = []
    validos = 0
    invalidos = 0
    
    for xml_file in xml_files:
        resultado = validar_xml_existente(xml_file)
        resultados.append(resultado)
        
        if resultado['success']:
            validos += 1
        else:
            invalidos += 1
    
    return {
        'total_archivos': len(xml_files),
        'validos': validos,
        'invalidos': invalidos,
        'resultados': resultados
    }
    """
    Genera claves de acceso para facturas que no las tienen
    Útil para corregir datos existentes
    """
    facturas_sin_clave = Factura.objects.filter(clave_acceso__isnull=True)
    integration = SRIIntegration()
    
    resultados = []
    for factura in facturas_sin_clave:
        try:
            # Generar clave de acceso
            clave_acceso = integration._generar_clave_acceso(factura)
            factura.clave_acceso = clave_acceso
            factura.save()
            
            resultados.append({
                'factura_id': factura.id,
                'numero': factura.numero,
                'clave_generada': clave_acceso,
                'success': True
            })
            
            logger.info(f"Clave generada para factura {factura.numero}: {clave_acceso}")
            
        except Exception as e:
            resultados.append({
                'factura_id': factura.id,
                'numero': factura.numero,
                'error': str(e),
                'success': False
            })
            
            logger.error(f"Error generando clave para factura {factura.numero}: {e}")
    
    return resultados
