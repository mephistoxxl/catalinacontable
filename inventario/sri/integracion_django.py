import os
import logging
import random
import time
import traceback
from datetime import datetime
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.utils import timezone
from inventario.models import Factura, DetalleFactura, Opciones
from inventario.tenant.queryset import set_current_tenant
from sistema.aws_utils import build_storage_url_or_none
from .sri_client import SRIClient
from .xml_generator import SRIXMLGenerator
from .pdf_firmador import PDFFirmador
from .ambiente import obtener_ambiente_sri

logger = logging.getLogger(__name__)

class SRIIntegration:
    """
    Clase de integración para conectar Django con el SRI
    """
    
    def __init__(self, empresa=None, tenant=None):
        """Inicializa la integración con el ambiente de la empresa"""
        if empresa is None and tenant is not None:
            empresa = tenant

        self.empresa = empresa

        try:
            ambiente = obtener_ambiente_sri(empresa)
            self.ambiente = 'produccion' if ambiente == '2' else 'pruebas'
        except Exception:
            self.ambiente = 'pruebas'

        self.cliente = SRIClient(ambiente=self.ambiente)

    def _get_factura(self, factura_id: int) -> Factura:
        """Obtiene factura de forma segura en contexto multi-tenant.

        - Si la integración fue inicializada con `empresa`, se fuerza el filtro por `empresa_id`
          usando el manager inseguro del modelo para evitar depender del thread-local tenant.
        - Si no hay `empresa`, mantiene el comportamiento anterior (puede depender del tenant actual).
        """
        if self.empresa is not None:
            return Factura._unsafe_objects.get(id=factura_id, empresa_id=getattr(self.empresa, 'id', None))
        return Factura.objects.get(id=factura_id)

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
            factura = self._get_factura(factura_id)
            # 🔐 Asegurar contexto tenant para managers multi-tenant
            try:
                set_current_tenant(getattr(factura, 'empresa', None))
            except Exception:
                logger.warning("No se pudo establecer tenant antes de enviar_factura")

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
            success = self._firmar_xml_xades_bes(xml_path, xml_firmado_path, factura.empresa)
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
            factura = self._get_factura(factura_id)
            try:
                set_current_tenant(getattr(factura, 'empresa', None))
            except Exception:
                logger.warning("No se pudo establecer tenant antes de procesar_factura")
            
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

            # Si ya fue enviada (evidencia: estado_sri RECIBIDA/PENDIENTE + mensajes SRI guardados), consultar autorización sin reenviar.
            # Importante: NO consultar solo por tener clave_acceso + estado_sri=PENDIENTE, porque eso puede ser un estado local
            # (o haber sido seteado por error) y terminaría "consultando" algo que nunca se envió.
            evidencia_envio = bool(getattr(factura, 'mensaje_sri', None) or getattr(factura, 'mensaje_sri_detalle', None))
            if (
                getattr(factura, 'clave_acceso', None)
                and hasattr(factura, 'estado_sri')
                and factura.estado_sri in ['RECIBIDA', 'PENDIENTE']
                and evidencia_envio
            ):
                estado_recep = factura.estado_sri
                resultado_auth = self.cliente.consultar_autorizacion(factura.clave_acceso)
                self._actualizar_factura_con_resultado(factura, resultado_auth, factura.clave_acceso)
                estado_auth = resultado_auth.get('estado')
                raw_response = resultado_auth.get('raw_response')
                # 🔧 FIX CRÍTICO: Reconocer tanto AUTORIZADA como AUTORIZADO en consulta
                if resultado_auth.get('estado') in ('AUTORIZADA', 'AUTORIZADO'):
                    self._generar_ride_autorizado(factura, resultado_auth)

                    email_res = None
                    try:
                        if hasattr(factura, 'email_enviado') and not factura.email_enviado:
                            email_res = self.enviar_factura_email(factura)
                    except Exception as e:
                        logger.warning(f"Fallo envío automático de email (consulta) para factura {factura.id}: {e}")

                    return {
                        'success': True,
                        'message': 'Factura autorizada exitosamente',
                        'resultado': resultado_auth,
                        'email': email_res,
                    }
                else:
                    logger.error(
                        "Autorización pendiente o rechazada - estado_recep=%s, estado_auth=%s, raw_response=%s",
                        estado_recep, estado_auth, raw_response
                    )
                    # Pendiente de autorización NO es un error; el SRI puede tardar.
                    return {
                        'success': True,
                        'message': 'Pendiente de autorización. Intente consultar nuevamente en unos minutos.',
                        'estado': 'PENDIENTE',
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

            # Desde aquí, vamos a intentar un envío real al SRI.
            if not factura.estado_sri or factura.estado_sri == '':
                try:
                    factura.estado_sri = 'PENDIENTE'
                    factura.save(update_fields=['estado_sri'])
                    logger.info(f"Factura {factura.id} cambió estado: LOCAL → PENDIENTE (iniciando envío real al SRI)")
                except Exception:
                    # No bloquear el envío por un fallo de guardado del estado
                    logger.warning(f"No se pudo actualizar estado_sri a PENDIENTE para factura {factura.id}")
            
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
            success = self._firmar_xml_xades_bes(xml_path, xml_firmado_path, factura.empresa)
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
                _, respuesta_autorizacion = self._evaluar_resultado_autorizacion(
                    factura,
                    resultado_auth,
                    clave_acceso,
                    estado_recep='RECIBIDA',
                    origen='recepcion_inmediata',
                )
                return respuesta_autorizacion
            else:
                # El comprobante no fue recibido correctamente
                mensajes_recep = resultado.get('mensajes', [])

                if self._mensajes_indican_clave_en_procesamiento(mensajes_recep):
                    return self._manejar_clave_en_procesamiento(factura, clave_acceso, mensajes_recep)

                mensaje_detalle = mensajes_recep[0].get('mensaje', 'Error desconocido') if mensajes_recep else 'Error desconocido'

                # Caso especial: SRI indica secuencial duplicado (código 45)
                try:
                    es_secuencial_registrado = any(
                        str(m.get('identificador', '')).strip() == '45'
                        or 'SECUENCIAL REGISTRADO' in str(m.get('mensaje', '')).upper()
                        for m in (mensajes_recep or [])
                    )
                except Exception:
                    es_secuencial_registrado = False

                if es_secuencial_registrado:
                    numero = f"{getattr(factura, 'establecimiento', '')}-{getattr(factura, 'punto_emision', '')}-{getattr(factura, 'secuencia', '')}".strip('-')
                    mensaje_detalle = (
                        f"El SRI reporta que el secuencial ya está registrado para esta serie. "
                        f"Número: {numero}. "
                        "Esto puede pasar si la secuencia local está desfasada (por ejemplo, se reinició, se migró desde otro sistema, "
                        "o ya se emitieron documentos con esa serie en el portal SRI). "
                        "Solución: en Configuración → Secuencias, ajuste el 'siguiente secuencial' a un número mayor al último emitido en el SRI "
                        "para esa serie y vuelva a emitir una nueva factura."
                    )

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

            # Intentar dejar trazabilidad en la factura (sin romper el handler por otro error)
            try:
                factura = self._get_factura(factura_id)
                campos = []
                if hasattr(factura, 'estado_sri') and factura.estado_sri != 'ERROR':
                    factura.estado_sri = 'ERROR'
                    campos.append('estado_sri')
                if hasattr(factura, 'mensaje_sri'):
                    factura.mensaje_sri = 'Error procesando envío/consulta SRI'
                    campos.append('mensaje_sri')
                if hasattr(factura, 'mensaje_sri_detalle'):
                    factura.mensaje_sri_detalle = str(e)
                    campos.append('mensaje_sri_detalle')
                if campos:
                    factura.save(update_fields=list(dict.fromkeys(campos)))
            except Exception:
                pass

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
        empresa = getattr(factura, 'empresa', None)
        opciones = Opciones.objects.for_tenant(empresa).first()
        if not opciones:
            if empresa:
                opciones = Opciones.objects.create(empresa=empresa, identificacion=empresa.ruc)
            else:
                raise ValueError("RUC no configurado en Opciones")
        ruc = opciones.identificacion.zfill(13)
        
        # 🔄 SINCRONIZAR con Opciones.tipo_ambiente
        try:
            opciones = Opciones.objects.for_tenant(empresa).first()
            if not opciones and empresa:
                opciones = Opciones.objects.create(empresa=empresa, identificacion=empresa.ruc)
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

    def _mensajes_indican_clave_en_procesamiento(self, mensajes):
        """Detecta si la respuesta del SRI menciona clave en procesamiento."""
        if not mensajes:
            return False
        for mensaje in mensajes:
            if isinstance(mensaje, dict):
                texto = " ".join([
                    str(mensaje.get('mensaje', '') or ''),
                    str(mensaje.get('informacionAdicional', '') or ''),
                    str(mensaje.get('detalle', '') or '')
                ])
            else:
                texto = str(mensaje or '')
            texto_upper = texto.upper()
            if 'CLAVE' in texto_upper and 'PROCESAMIENTO' in texto_upper:
                return True
        return False

    def _evaluar_resultado_autorizacion(self, factura, resultado_auth, clave_acceso, estado_recep='RECIBIDA', origen='consulta', mensaje_pendiente=None):
        """Normaliza la respuesta de autorización y arma la estructura final."""
        self._actualizar_factura_con_resultado(factura, resultado_auth, clave_acceso)

        estado_bruto = resultado_auth.get('estado', '')
        estado_auth = str(estado_bruto or '').upper().strip()
        if not estado_auth:
            estado_auth = 'PENDIENTE'

        raw_response = resultado_auth.get('raw_response')
        logger.info(
            "Evaluando autorización SRI | clave=%s | estado_recep=%s | estado_auth=%s | origen=%s",
            clave_acceso,
            estado_recep,
            estado_auth,
            origen,
        )

        estados_pendientes = {
            'PENDIENTE',
            'EN_PROCESO',
            'EN_PROCESAMIENTO',
            'PROCESANDO',
            'PROCESAMIENTO',
            'RECIBIDA',
        }

        if estado_auth in ('AUTORIZADA', 'AUTORIZADO'):
            self._generar_ride_autorizado(factura, resultado_auth)

            email_res = None
            try:
                if hasattr(factura, 'email_enviado') and not factura.email_enviado:
                    email_res = self.enviar_factura_email(factura)
            except Exception as exc:
                logger.warning(
                    "Fallo envío automático de email (%s) para factura %s: %s",
                    origen,
                    factura.id,
                    exc,
                )

            return estado_auth, {
                'success': True,
                'message': 'Factura autorizada exitosamente',
                'resultado': resultado_auth,
                'estado': 'AUTORIZADA',
                'email': email_res,
            }

        if estado_auth in estados_pendientes:
            mensajes_auth = resultado_auth.get('mensajes', []) or []
            if mensaje_pendiente:
                mensaje_detalle = mensaje_pendiente
            else:
                mensaje_detalle = (
                    mensajes_auth[0].get('mensaje', 'El comprobante está pendiente de autorización')
                    if mensajes_auth and isinstance(mensajes_auth[0], dict)
                    else 'El comprobante está pendiente de autorización'
                )
            logger.info(
                "Autorización pendiente | clave=%s | mensaje=%s | raw=%s",
                clave_acceso,
                mensaje_detalle,
                raw_response,
            )
            return 'PENDIENTE', {
                'success': True,
                'message': f"Pendiente de autorización: {mensaje_detalle}. Intente nuevamente en unos minutos.",
                'estado': 'PENDIENTE',
                'resultado': resultado_auth,
            }

        mensajes_auth = resultado_auth.get('mensajes', []) or []
        if mensajes_auth and isinstance(mensajes_auth[0], dict):
            mensaje_detalle = mensajes_auth[0].get('mensaje', 'Error desconocido')
        else:
            mensaje_detalle = str(mensajes_auth[0]) if mensajes_auth else 'Error desconocido'

        logger.error(
            "Error en autorización | clave=%s | estado_recep=%s | estado_auth=%s | raw=%s",
            clave_acceso,
            estado_recep,
            estado_auth,
            raw_response,
        )

        return estado_auth, {
            'success': False,
            'message': f"Error en autorización: {mensaje_detalle}",
            'resultado': resultado_auth,
            'estado': estado_auth,
        }

    def _manejar_clave_en_procesamiento(self, factura, clave_acceso, mensajes_recep):
        """Reintenta la consulta cuando el SRI reporta clave en procesamiento."""
        logger.info(
            "Clave en procesamiento detectada | factura=%s | clave=%s",
            factura.id,
            clave_acceso,
        )

        esperas = [3, 6, 9]
        ultimo_resultado = None

        for intento, espera in enumerate(esperas, start=1):
            logger.info(
                "Reintento autorización %s/%s tras %ss | clave=%s",
                intento,
                len(esperas),
                espera,
                clave_acceso,
            )
            time.sleep(max(0, espera))
            resultado_auth = self.cliente.consultar_autorizacion(clave_acceso)
            estado_auth, respuesta = self._evaluar_resultado_autorizacion(
                factura,
                resultado_auth,
                clave_acceso,
                estado_recep='EN_PROCESAMIENTO',
                origen=f'reintento_{intento}',
                mensaje_pendiente='El SRI sigue procesando la clave de acceso',
            )

            if estado_auth in ('AUTORIZADA', 'AUTORIZADO'):
                return respuesta

            ultimo_resultado = respuesta

            if estado_auth not in {
                'PENDIENTE',
                'EN_PROCESO',
                'EN_PROCESAMIENTO',
                'PROCESANDO',
                'PROCESAMIENTO',
                'RECIBIDA',
            }:
                return respuesta

        # Mantener la factura marcada como pendiente para reintentos externos
        try:
            campos = []
            if hasattr(factura, 'estado') and factura.estado != 'PENDIENTE':
                factura.estado = 'PENDIENTE'
                campos.append('estado')
            if hasattr(factura, 'estado_sri') and factura.estado_sri != 'PENDIENTE':
                factura.estado_sri = 'PENDIENTE'
                campos.append('estado_sri')
            if hasattr(factura, 'mensaje_sri'):
                factura.mensaje_sri = 'Pendiente: Clave de acceso en procesamiento'
                campos.append('mensaje_sri')
            if hasattr(factura, 'mensaje_sri_detalle'):
                factura.mensaje_sri_detalle = str(mensajes_recep or [])
                campos.append('mensaje_sri_detalle')
            if campos:
                factura.save(update_fields=list(dict.fromkeys(campos)))
        except Exception as exc:
            logger.warning(
                "No se pudo actualizar mensaje pendiente para factura %s: %s",
                factura.id,
                exc,
            )

        if ultimo_resultado and ultimo_resultado.get('resultado'):
            resultado_base = ultimo_resultado.get('resultado')
        else:
            resultado_base = {
                'estado': 'PENDIENTE',
                'mensajes': mensajes_recep or [],
            }

        primer_mensaje = ''
        if mensajes_recep:
            msg0 = mensajes_recep[0]
            if isinstance(msg0, dict):
                primer_mensaje = msg0.get('mensaje') or msg0.get('informacionAdicional') or ''
            else:
                primer_mensaje = str(msg0)

        mensaje_usuario = 'El SRI sigue procesando la clave de acceso. Verificaremos nuevamente automáticamente.'
        if primer_mensaje:
            mensaje_usuario += f" Mensaje SRI: {primer_mensaje}."

        return {
            'success': True,
            'message': mensaje_usuario,
            'estado': 'PENDIENTE',
            'resultado': resultado_base,
        }
    
    def _actualizar_factura_con_resultado(self, factura, resultado, clave_acceso):
        """
        Actualiza la factura con el resultado del SRI
        
        Args:
            factura: Instancia de Factura
            resultado: Dict con resultado del SRI
            clave_acceso: Clave de acceso (solo para verificación, no para sobrescribir)
        """
        estado_sri_anterior = (getattr(factura, 'estado_sri', '') or '').upper().strip()
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
        mensajes_resultado = resultado.get('mensajes', []) or []

        # ✅ IMPORTANTE: errores de conexión del SRI suelen ser temporales (p.ej. ConnectionResetError 10054)
        # y NO deben marcar la factura como ERROR final porque cortaría el polling.
        try:
            es_error_conexion = any(
                isinstance(m, dict) and str(m.get('identificador', '')).strip().upper() in {'CONNECTION_ERROR', 'TRANSPORT_ERROR'}
                for m in (mensajes_resultado or [])
            )
        except Exception:
            es_error_conexion = False

        if estado_normalizado == 'ERROR' and es_error_conexion:
            # Mantener el estado anterior si ya estaba en un estado temporal.
            if estado_sri_anterior in ('RECIBIDA', 'PENDIENTE'):
                logger.warning(
                    "Error de conexión consultando SRI (factura %s). Se mantiene estado temporal %s.",
                    getattr(factura, 'id', 'N/D'),
                    estado_sri_anterior,
                )
                estado_normalizado = estado_sri_anterior
                estado = estado_sri_anterior
            else:
                logger.warning(
                    "Error de conexión consultando SRI (factura %s). Se normaliza a PENDIENTE para reintentar.",
                    getattr(factura, 'id', 'N/D'),
                )
                estado_normalizado = 'PENDIENTE'
                estado = 'PENDIENTE'

        if estado_normalizado in ('DEVUELTA', 'ERROR') and self._mensajes_indican_clave_en_procesamiento(mensajes_resultado):
            logger.info(
                "Estado %s normalizado a PENDIENTE por reporte 'clave en procesamiento'",
                estado_normalizado,
            )
            estado_normalizado = 'PENDIENTE'
            estado = 'PENDIENTE'
        
        logger.info(f"Actualizando factura {factura.id} con estado SRI: '{estado}' (normalizado: '{estado_normalizado}')")

        # 🔧 FIX: Manejo completo de estados AUTORIZADA/AUTORIZADO
        if estado_normalizado in ('AUTORIZADA', 'AUTORIZADO'):
            if hasattr(factura, 'estado'):
                factura.estado = 'AUTORIZADO'
            if hasattr(factura, 'estado_sri'):
                factura.estado_sri = 'AUTORIZADA'
            if hasattr(factura, 'mensaje_sri'):
                factura.mensaje_sri = 'Comprobante autorizado'
                
            # Obtener datos de autorización en distintas variantes de estructura
            aut = None

            autorizaciones = resultado.get('autorizaciones')
            if autorizaciones:
                if isinstance(autorizaciones, list):
                    aut = autorizaciones[0]
                elif isinstance(autorizaciones, dict):
                    aut_data = autorizaciones.get('autorizacion', autorizaciones)
                    if isinstance(aut_data, list):
                        aut = aut_data[0]
                    else:
                        aut = aut_data
                else:
                    aut_data = getattr(autorizaciones, 'autorizacion', autorizaciones)
                    aut = aut_data[0] if isinstance(aut_data, list) else aut_data

            if aut is None:
                autorizacion = resultado.get('autorizacion')
                if autorizacion:
                    aut = autorizacion[0] if isinstance(autorizacion, list) else autorizacion

            if aut is None:
                numero = resultado.get('numeroAutorizacion') or resultado.get('numero_autorizacion')
                fecha = resultado.get('fechaAutorizacion') or resultado.get('fecha_autorizacion')
                comprobante = resultado.get('comprobante') or resultado.get('xml_autorizado')
                if numero or fecha or comprobante:
                    aut = {
                        'numeroAutorizacion': numero,
                        'fechaAutorizacion': fecha,
                        'comprobante': comprobante,
                    }

            if aut:
                # 🔍 DEBUG: Ver qué datos trae la autorización
                logger.info(f"🔍 Datos de autorización recibidos del SRI: {aut}")
                
                if hasattr(factura, 'numero_autorizacion'):
                    numero_aut = aut.get('numeroAutorizacion') or aut.get('numero_autorizacion')
                    factura.numero_autorizacion = numero_aut
                    if not numero_aut:
                        logger.warning(
                            f"Factura {factura.id} autorizada sin numeroAutorizacion en resultado"
                        )
                if hasattr(factura, 'fecha_autorizacion'):
                    fecha_str = aut.get('fechaAutorizacion') or aut.get('fecha_autorizacion')
                    logger.info(f"🔍 Fecha de autorización del SRI (raw): {fecha_str}")
                    logger.info(f"🔍 Tipo de dato recibido: {type(fecha_str)}")
                    if fecha_str:
                        try:
                            from datetime import datetime
                            from django.utils import timezone
                            
                            # El SRI envía varios formatos posibles:
                            # 1. ISO 8601: "2015-05-21T14:22:30.764-05:00" (con milisegundos y timezone)
                            # 2. ISO simple: "2025-11-16T06:00:06"
                            # 3. Formato local: "16/11/2025 06:00:06"
                            
                            fecha_dt = None
                            fecha_str_trabajo = str(fecha_str).strip()
                            
                            # ✅ Normalizar formato: espacio → T (algunos servicios usan espacio)
                            # "2025-11-10 15:10:32-05:00" → "2025-11-10T15:10:32-05:00"
                            if ' ' in fecha_str_trabajo and ('-' in fecha_str_trabajo.split(' ')[-1] or '+' in fecha_str_trabajo.split(' ')[-1]):
                                # Tiene espacio y timezone, reemplazar espacio por T
                                fecha_str_trabajo = fecha_str_trabajo.replace(' ', 'T', 1)
                            
                            if 'T' in fecha_str_trabajo:
                                # Formato ISO con T
                                fecha_limpia = fecha_str_trabajo
                                
                                # Manejar diferentes variantes ISO
                                if '-05:00' in fecha_limpia or '+' in fecha_limpia or 'Z' in fecha_limpia:
                                    # ISO 8601 completo con timezone
                                    fecha_limpia = fecha_limpia.replace('Z', '+00:00')
                                    # Remover milisegundos si existen (ej: .764)
                                    if '.' in fecha_limpia:
                                        partes = fecha_limpia.split('.')
                                        # Mantener solo timezone después del punto
                                        if len(partes) == 2:
                                            # partes[0] = "2015-05-21T14:22:30"
                                            # partes[1] = "764-05:00"
                                            timezone_part = partes[1]
                                            # Extraer solo el timezone
                                            if '-' in timezone_part:
                                                tz = '-' + timezone_part.split('-')[1]
                                            elif '+' in timezone_part:
                                                tz = '+' + timezone_part.split('+')[1]
                                            else:
                                                tz = ''
                                            fecha_limpia = partes[0] + tz
                                    
                                    fecha_dt = datetime.fromisoformat(fecha_limpia)
                                    # ✅ IMPORTANTE: El SRI envía hora de Ecuador con -05:00
                                    # Quitamos el timezone y lo tratamos como hora local de Ecuador
                                    import pytz
                                    ecuador_tz = pytz.timezone('America/Guayaquil')
                                    if fecha_dt.tzinfo is not None:
                                        # Convertir a hora naive (sin timezone) manteniendo la hora
                                        fecha_dt = fecha_dt.replace(tzinfo=None)
                                    # Ahora localizamos como hora de Ecuador
                                    fecha_dt = ecuador_tz.localize(fecha_dt)
                                else:
                                    # ISO simple sin timezone
                                    fecha_dt = datetime.fromisoformat(fecha_limpia)
                                    # Hacer timezone-aware en Ecuador
                                    import pytz
                                    ecuador_tz = pytz.timezone('America/Guayaquil')
                                    if fecha_dt.tzinfo is None:
                                        fecha_dt = ecuador_tz.localize(fecha_dt)
                            
                            elif '/' in fecha_str_trabajo:
                                # Formato SRI local: "16/11/2025 06:00:06"
                                fecha_dt = datetime.strptime(fecha_str_trabajo, '%d/%m/%Y %H:%M:%S')
                                # Hacer timezone-aware en Ecuador
                                import pytz
                                ecuador_tz = pytz.timezone('America/Guayaquil')
                                fecha_dt = ecuador_tz.localize(fecha_dt)
                            
                            if fecha_dt:
                                factura.fecha_autorizacion = fecha_dt
                                logger.info(f"✅ Fecha autorización ASIGNADA al objeto: {factura.fecha_autorizacion}")
                                logger.info(f"   Tipo: {type(factura.fecha_autorizacion)}")
                            else:
                                logger.warning(f"⚠️ No se pudo parsear fecha: {fecha_str}")
                                factura.fecha_autorizacion = None
                            
                        except Exception as e:
                            logger.error(
                                f"❌ Error parseando fecha autorización: {fecha_str} - Error: {e}"
                            )
                            logger.error(f"Traceback completo:")
                            traceback.print_exc()
                            factura.fecha_autorizacion = None
                    else:
                        logger.warning(
                            f"Factura {factura.id} autorizada sin fechaAutorizacion en resultado"
                        )
                        factura.fecha_autorizacion = None
                if hasattr(factura, 'xml_autorizado'):
                    xml_aut = aut.get('comprobante') or aut.get('xml_autorizado')
                    if xml_aut:
                        factura.xml_autorizado = xml_aut or factura.xml_autorizado
                    else:
                        logger.warning(
                            f"Factura {factura.id} autorizada sin XML de comprobante en resultado"
                        )
            else:
                logger.warning(
                    f"Factura {factura.id} autorizada pero sin datos de autorización; se recomienda reconsultar"
                )
            
            logger.info(f"Factura {factura.id} marcada como AUTORIZADA")

        # 🔧 FIX: Manejo completo de estados de rechazo
        elif estado_normalizado in ('NO_AUTORIZADA', 'RECHAZADA', 'NO_AUTORIZADO', 'DEVUELTA'):
            if hasattr(factura, 'estado'):
                factura.estado = 'RECHAZADO'
            if hasattr(factura, 'estado_sri'):
                factura.estado_sri = 'RECHAZADA'
            if hasattr(factura, 'mensaje_sri'):
                mensaje_detalle = (
                    mensajes_resultado[0].get('mensaje', 'Comprobante rechazado')
                    if mensajes_resultado and isinstance(mensajes_resultado[0], dict)
                    else 'Comprobante rechazado'
                )
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
                if mensajes_resultado and isinstance(mensajes_resultado[0], dict):
                    mensaje_detalle = mensajes_resultado[0].get('mensaje', 'Pendiente de autorización')
                else:
                    mensaje_detalle = 'Pendiente de autorización'
                factura.mensaje_sri = f"Pendiente: {mensaje_detalle}"
            
            logger.info(f"Factura {factura.id} marcada como PENDIENTE")

        else:  # ERROR y otros estados
            if hasattr(factura, 'estado'):
                factura.estado = 'ERROR'
            if hasattr(factura, 'estado_sri'):
                factura.estado_sri = 'ERROR'
            if hasattr(factura, 'mensaje_sri'):
                if mensajes_resultado and isinstance(mensajes_resultado[0], dict):
                    mensaje_error = mensajes_resultado[0].get('mensaje', 'Error desconocido')
                else:
                    mensaje_error = 'Error desconocido'
                factura.mensaje_sri = f"Error: {mensaje_error}"
            
            logger.warning(f"Factura {factura.id} marcada como ERROR - Estado desconocido: {estado}")
        
        # 🔧 FIX: Guardar mensajes completos si el campo existe
        if hasattr(factura, 'mensaje_sri_detalle'):
            mensajes_detalle = mensajes_resultado
            factura.mensaje_sri_detalle = None if not mensajes_detalle else str(mensajes_detalle)
        
        # 🔧 FIX: SIEMPRE guardar los cambios
        logger.info(f"💾 Guardando factura {factura.id} en BD...")
        logger.info(f"   ANTES DE SAVE - fecha_autorizacion: {factura.fecha_autorizacion}")
        factura.save()
        
        # 🔍 VERIFICACIÓN POST-SAVE: Re-cargar desde BD para confirmar
        factura.refresh_from_db()
        logger.info(f"✅ Factura {factura.id} guardada y verificada en BD")
        logger.info(f"   📅 fecha_autorizacion (desde BD): {factura.fecha_autorizacion}")
        logger.info(f"   📅 fecha_emision (desde BD): {factura.fecha_emision}")
        logger.info(f"   🔢 numero_autorizacion (desde BD): {factura.numero_autorizacion}")
        logger.info(f"   📊 estado_sri (desde BD): {factura.estado_sri}")

        # ✅ NUEVO: si recién pasó a RECIBIDA, encolar polling cada 30s hasta AUTORIZADA/RECHAZADA
        try:
            estado_sri_actual = (getattr(factura, 'estado_sri', '') or '').upper().strip()
            if estado_sri_anterior != 'RECIBIDA' and estado_sri_actual == 'RECIBIDA':
                from inventario.sri.rq_jobs import enqueue_poll_autorizacion_factura

                enqueue_poll_autorizacion_factura(
                    factura_id=int(factura.id),
                    empresa_id=int(getattr(factura, 'empresa_id', factura.empresa.id)),
                    delay_seconds=30,
                    attempt=1,
                )
        except Exception as exc:
            logger.warning(
                "No se pudo encolar polling de autorización para factura %s: %s",
                getattr(factura, 'id', None),
                exc,
            )
    
    def _firmar_xml_xades_bes(self, xml_path, xml_firmado_path, empresa=None):
        """Firma un XML utilizando el esquema XAdES-BES."""
        try:
            from .firmador_xades_sri import firmar_xml_xades_bes, XAdESError
            firmar_xml_xades_bes(xml_path, xml_firmado_path, empresa=empresa)
            logger.info("XML firmado exitosamente con XAdES-BES")
            return True
        except XAdESError as xe:
            # Error esperado de configuración incompleta: propagar texto limpio
            logger.error(f"Fallo de configuración firma: {xe}")
            raise Exception(str(xe))
        except Exception as e:
            logger.error(f"Error crítico en proceso de firma: {e}")
            raise Exception(f"Proceso de firma falló: {e}")
    
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
            # ✅ generar_ride_factura_firmado ya guarda en storage y retorna la ruta
            saved_path = ride_gen.generar_ride_factura_firmado(factura, firmar=False)
            
            # Actualizar factura con ruta del RIDE
            if hasattr(factura, 'ride_autorizado'):
                factura.ride_autorizado = saved_path
                factura.save(update_fields=['ride_autorizado'])
            
            logger.info(f"✅ RIDE generado y guardado: {saved_path}")
            
        except Exception as e:
            logger.error(f"❌ Error generando RIDE: {e}")
            raise  # Re-lanzar la excepción para que se maneje arriba
    def enviar_factura_email(self, factura):
        """
        Envía por correo electrónico el RIDE y XML autorizado de una factura.

        Args:
            factura (Factura): instancia de factura ya autorizada.

        Returns:
            dict: resultado del envío con ``success`` y ``message``.
        """
        try:
            # Verificar autorización (SIN consultar al SRI para evitar bucles)
            if factura.estado_sri != 'AUTORIZADA':
                return {'success': False, 'message': f'La factura no está autorizada. Estado actual: {factura.estado_sri}'}

            empresa = getattr(factura, 'empresa', None)
            opciones = Opciones.objects.for_tenant(empresa).first()
            if not opciones:
                if empresa:
                    opciones = Opciones.objects.create(empresa=empresa, identificacion=empresa.ruc)
                else:
                    return {'success': False, 'message': 'No se encontraron opciones de empresa'}

            # Asegurar existencia de RIDE autorizado
            if not getattr(factura, 'ride_autorizado', None):
                try:
                    self._generar_ride_autorizado(factura, {'numero_autorizacion': factura.numero_autorizacion})
                    factura.refresh_from_db()  # Refrescar para obtener el campo actualizado
                except Exception as e:
                    logger.error(f"Error generando RIDE para email: {e}")
                    return {'success': False, 'message': f'No se pudo generar RIDE: {str(e)}'}

            # Verificar nuevamente después del intento
            if not getattr(factura, 'ride_autorizado', None):
                return {'success': False, 'message': 'No se pudo generar RIDE autorizado'}

            # Preparar datos para el template
            from django.template.loader import render_to_string
            from datetime import datetime
            
            # ✅ USAR NOMBRE COMERCIAL si existe
            nombre_comercial = getattr(opciones, 'nombre_comercial', '')
            razon_social = getattr(opciones, 'razon_social', '')
            nombre_emisor = nombre_comercial if nombre_comercial and nombre_comercial != '[CONFIGURAR NOMBRE COMERCIAL]' else razon_social
            
            numero_factura = f"{factura.establecimiento}-{factura.punto_emision}-{factura.secuencia}"
            
            asunto = f"Factura Electrónica {numero_factura} - {nombre_emisor}"
            
            destinatario = getattr(factura.cliente, 'correo', None)
            if not destinatario:
                return {'success': False, 'message': 'El cliente no tiene correo registrado'}

            # Contexto para el template HTML
            # Determinar URL del logo - usar imagen de opciones si existe
            logo_url = None
            if hasattr(opciones, 'imagen') and opciones.imagen:
                logo_url = build_storage_url_or_none(opciones.imagen)
                if logo_url:
                    logger.info(f"� Usando logo de opciones firmado temporalmente")

            if not logo_url:
                # Logo de CATALINA (sistema) por defecto
                logo_url = 'https://catalina-media-prod.s3.us-east-2.amazonaws.com/static/inventario/assets/logo/logo-catalina.png'
                logger.info(f"📸 Usando logo CATALINA por defecto: {logo_url}")
            
            context = {
                'nombre_cliente': factura.nombre_cliente,
                'razon_social': nombre_emisor,  # ✅ Usar nombre comercial
                'ruc': opciones.identificacion,
                'numero_factura': numero_factura,
                'fecha_emision': factura.fecha_emision.strftime('%d/%m/%Y'),
                'fecha_autorizacion': factura.fecha_autorizacion.strftime('%d/%m/%Y %H:%M:%S') if factura.fecha_autorizacion else 'N/A',
                'clave_acceso': factura.clave_acceso,
                'total': f"{factura.monto_general:.2f}",
                'ambiente': 'Pruebas' if getattr(empresa, 'tipo_ambiente', '1') == '1' else 'Producción',
                'nombre_sistema': 'Catalina Facturador',
                'email_empresa': getattr(opciones, 'correo', ''),
                'telefono': getattr(opciones, 'telefono', ''),
                'year': datetime.now().year,
                'logo_url': logo_url,
                # Redes sociales (puedes agregar estos campos a Opciones si quieres)
                'facebook_url': None,
                'youtube_url': None,
                'instagram_url': None,
                'nombre_emisor': nombre_emisor,  # ✅ Agregar al contexto
            }
            
            # Renderizar HTML
            html_content = render_to_string('emails/factura_autorizada.html', context)
            
            # Texto plano alternativo (fallback)
            texto_plano = f"""
Estimado/a {factura.nombre_cliente},

Se ha emitido un comprobante electrónico con su nombre. El documento se encuentra autorizado por el SRI.

Emisor: {nombre_emisor}
RUC: {opciones.identificacion}
Factura No: {numero_factura}
Fecha de Emisión: {factura.fecha_emision.strftime('%d/%m/%Y')}
Clave de Acceso: {factura.clave_acceso}
Total: ${factura.monto_general:.2f}

Adjunto encontrará el RIDE (PDF) y el XML autorizado.

Saludos cordiales,
{nombre_emisor}
"""

            # 🔧 FIX: Usar dominio verificado de Zeptomail (no Gmail)
            # Remitente simple sin nombre de empresa
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@catalinasoft-ec.com')
            
            # Reply-to con el correo de la empresa
            reply_to_email = getattr(opciones, 'correo', None)

            # Crear email con HTML
            from django.core.mail import EmailMultiAlternatives
            email = EmailMultiAlternatives(
                asunto,
                texto_plano,
                from_email=from_email,
                to=[destinatario],
                reply_to=[reply_to_email] if reply_to_email else None,
            )
            email.attach_alternative(html_content, "text/html")

            # Adjuntar RIDE PDF - Generar directamente en memoria para evitar problemas con S3
            ride_attached = False
            try:
                logger.info("Generando RIDE en memoria para adjuntar al email...")
                from ..sri.ride_generator import RIDEGenerator
                
                ride_gen = RIDEGenerator()
                
                # Generar RIDE en memoria (sin guardar en S3)
                detalles = factura.detallefactura_set.all()
                pdf_bytes = ride_gen.generar_ride_factura(
                    factura,
                    detalles,
                    opciones,
                    None,  # No guardar en archivo, solo retornar bytes
                    clave_acceso=factura.clave_acceso,
                )
                
                email.attach(f"RIDE_{numero_factura}.pdf", pdf_bytes, 'application/pdf')
                logger.info(f"✅ RIDE generado y adjuntado: {len(pdf_bytes)} bytes")
                ride_attached = True
            except Exception as e:
                logger.error(f"❌ Error generando RIDE para adjuntar: {e}")
                import traceback
                traceback.print_exc()

            if not ride_attached:
                logger.warning("⚠️ No se pudo adjuntar el RIDE PDF al email")

            # Adjuntar XML autorizado
            if factura.xml_autorizado:
                xml_file = ContentFile(factura.xml_autorizado.encode('utf-8'))
                email.attach(f"Factura_{numero_factura}.xml", xml_file.read(), 'application/xml')

            email.send(fail_silently=False)

            # Marcar envío en la factura (si existen campos)
            try:
                update_fields = []
                if hasattr(factura, 'email_enviado') and not factura.email_enviado:
                    factura.email_enviado = True
                    update_fields.append('email_enviado')
                if hasattr(factura, 'email_enviado_at'):
                    factura.email_enviado_at = timezone.now()
                    update_fields.append('email_enviado_at')
                if hasattr(factura, 'email_envio_intentos'):
                    factura.email_envio_intentos = (factura.email_envio_intentos or 0) + 1
                    update_fields.append('email_envio_intentos')
                if hasattr(factura, 'email_ultimo_error'):
                    factura.email_ultimo_error = None
                    update_fields.append('email_ultimo_error')
                if update_fields:
                    factura.save(update_fields=update_fields)
            except Exception as e:
                logger.warning(f"No se pudo actualizar tracking de email en factura {getattr(factura,'id',None)}: {e}")

            return {'success': True, 'message': 'Factura enviada por correo exitosamente'}
        except Exception as e:
            logger.error(f"Error enviando factura por correo: {e}")
            # Registrar intento fallido en la factura (si existen campos)
            try:
                update_fields = []
                if hasattr(factura, 'email_envio_intentos'):
                    factura.email_envio_intentos = (factura.email_envio_intentos or 0) + 1
                    update_fields.append('email_envio_intentos')
                if hasattr(factura, 'email_ultimo_error'):
                    factura.email_ultimo_error = str(e)
                    update_fields.append('email_ultimo_error')
                if update_fields:
                    factura.save(update_fields=update_fields)
            except Exception:
                pass
            return {'success': False, 'message': str(e)}

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
            factura = self._get_factura(factura_id)
            
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

                # 📧 Envío automático de email si está autorizada y aún no se envió
                try:
                    if hasattr(factura, 'email_enviado') and not factura.email_enviado:
                        self.enviar_factura_email(factura)
                except Exception as e:
                    logger.warning(f"Fallo envío automático de email (consultar_estado_factura) para factura {factura.id}: {e}")

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
            factura = self._get_factura(factura_id)
            
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
