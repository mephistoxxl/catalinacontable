# inventario/sri/xml_generator.py

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from decimal import Decimal
import logging
import re
import os
from lxml import etree
logger = logging.getLogger(__name__)


class SRIXMLGenerator:
    """
    Generador de XML para comprobantes electrónicos según ficha técnica SRI Ecuador v2.31
    
    IMPORTANTE: Este generador NO duplica lógica. Solo lee datos de los modelos Django
    que ya tienen toda la lógica implementada (clave de acceso, cálculos, validaciones, etc.)
    """

    def validar_xml_contra_xsd(self, xml_content, xsd_path):
        """
        Valida el XML contra el XSD oficial del SRI.
        
        Args:
            xml_content (str): Contenido XML a validar
            xsd_path (str): Ruta al archivo XSD
            
        Returns:
            dict: {
                'valido': bool,
                'mensaje': str,
                'errores': str (si hay errores)
            }
        """
        try:
            from lxml import etree
            
            # Verificar que el archivo XSD existe
            if not os.path.exists(xsd_path):
                raise FileNotFoundError(f"Archivo XSD no encontrado: {xsd_path}")
            
            # Cargar esquemas dependientes primero (xmldsig)
            sri_dir = os.path.dirname(xsd_path)
            xmldsig_path = os.path.join(sri_dir, 'xmldsig-core-schema.xsd')
            
            # Cargar el esquema XSD principal con resolución de imports
            with open(xsd_path, 'rb') as xsd_file:
                # Crear un resolver personalizado para los esquemas
                class SchemaResolver(etree.Resolver):
                    def resolve(self, url, id, context):
                        if 'xmldsig' in url or 'xmldsig-core-schema' in url:
                            if os.path.exists(xmldsig_path):
                                return self.resolve_filename(xmldsig_path, context)
                        return None
                
                parser = etree.XMLParser()
                parser.resolvers.add(SchemaResolver())
                
                try:
                    schema_doc = etree.parse(xsd_file, parser)
                    schema = etree.XMLSchema(schema_doc)
                except etree.XMLSchemaParseError as e:
                    # Si falla con resolver, intentar sin él
                    xsd_file.seek(0)
                    schema_root = etree.XML(xsd_file.read())
                    schema = etree.XMLSchema(schema_root)
            
            # Parsear el XML
            try:
                # Si xml_content es una ruta de archivo, leer el archivo
                if os.path.isfile(xml_content):
                    with open(xml_content, 'rb') as xml_file:
                        xml_doc = etree.parse(xml_file)
                else:
                    # Si es contenido XML como string
                    xml_doc = etree.fromstring(xml_content.encode('utf-8'))
            except etree.XMLSyntaxError as e:
                return {
                    'valido': False,
                    'mensaje': 'Error de sintaxis XML',
                    'errores': f"Error de sintaxis en línea {e.lineno}: {e.msg}"
                }
            
            # Validar contra el esquema
            if schema.validate(xml_doc):
                return {
                    'valido': True,
                    'mensaje': 'XML válido según el esquema XSD del SRI'
                }
            else:
                # Crear mensaje de error detallado
                errores = []
                for error in schema.error_log:
                    errores.append(f"Línea {error.line}: {error.message}")
                
                mensaje_error = "El XML no cumple con el XSD del SRI:\n" + "\n".join(errores)
                return {
                    'valido': False,
                    'mensaje': 'XML inválido',
                    'errores': mensaje_error
                }
            
        except Exception as e:
            # Re-raise con contexto adicional
            raise Exception(f"Error validando XML contra XSD: {str(e)}")
    def __init__(self, ambiente=None):
        # NOTA: El parámetro ambiente se ignora porque se lee de Opciones.tipo_ambiente
        # Se mantiene por compatibilidad con código existente
        if ambiente:
            logger.warning(
                "El parámetro 'ambiente' en SRIXMLGenerator está deprecado. "
                "El ambiente se lee de Opciones.tipo_ambiente"
            )
        
        # Namespaces requeridos por SRI
        self.namespaces = {
            'xmlns:ds': 'http://www.w3.org/2000/09/xmldsig#',
            'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
    
    def _limpiar_texto(self, texto):
        """
        Limpia texto para XML según especificaciones del SRI
        - No permite saltos de línea (pattern [^\n]*)
        - Elimina espacios múltiples
        - No escapa caracteres especiales XML (el XML library lo hace automáticamente)
        """
        if not texto:
            return ""
        
        # Convertir a string y eliminar saltos de línea
        texto = str(texto).replace('\n', ' ').replace('\r', ' ')
        
        # Eliminar espacios múltiples
        texto = re.sub(r'\s+', ' ', texto)
        
        return texto.strip()
    
    def _formatear_decimal(self, valor, decimales=2):
        """
        Formatea decimal para XML según especificaciones del SRI
        """
        if valor is None:
            valor = 0
        
        # Si ya es string formateado correctamente, retornar
        if isinstance(valor, str) and '.' in valor:
            try:
                partes = valor.split('.')
                if len(partes[1]) == decimales:
                    return valor
            except:
                pass
        
        # Convertir a Decimal y formatear
        decimal_val = Decimal(str(valor))
        formato = f"{{:.{decimales}f}}"
        return formato.format(decimal_val)
    
    def _formatear_fecha(self, fecha):
        """Formatea fecha al formato dd/mm/aaaa requerido por SRI"""
        if isinstance(fecha, str):
            # Si ya está en formato correcto, retornar
            if re.match(r'\d{2}/\d{2}/\d{4}', fecha):
                return fecha
        
        # Si es objeto fecha, formatear
        if hasattr(fecha, 'strftime'):
            return fecha.strftime("%d/%m/%Y")
        
        raise ValueError(f"Formato de fecha inválido: {fecha}")

    def generar_xml_factura(self, factura):
        """
        Genera XML de factura a partir del modelo Factura de Django
        MEJORADO: Espera a que las formas de pago estén completamente guardadas
        
        Args:
            factura: Instancia del modelo Factura con todos sus relacionados cargados
            
        Returns:
            String con el XML generado
        """
        try:
            logger.info(f"Generando XML para factura {factura.id}")

            # ❗ Validar inmediatamente que existan formas de pago
            factura.refresh_from_db()
            if not factura.formas_pago.exists():
                error_msg = (
                    f"❌ ERROR CRÍTICO: Factura {factura.id} no tiene formas de pago registradas. "
                    "TODAS las facturas DEBEN registrar sus formas de pago antes de generar XML."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.debug(
                f"Establecimiento: {factura.establecimiento}, Punto emisión: {factura.punto_emision}, Secuencial: {factura.secuencia}"
            )
            
            # Obtener datos del emisor desde Opciones
            from inventario.models import Opciones
            emisor = Opciones.objects.first()
            if not emisor:
                raise ValueError("No existe configuración de empresa (Opciones)")
            
            # Verificar configuración del emisor
            if (getattr(emisor, 'identificacion', '0000000000000') == '0000000000000' or 
                '[CONFIGURAR' in getattr(emisor, 'razon_social', '') or
                '[CONFIGURAR' in getattr(emisor, 'direccion_establecimiento', '') or
                getattr(emisor, 'correo', 'configurar@empresa.com') == 'configurar@empresa.com' or
                getattr(emisor, 'telefono', '0000000000') == '0000000000'):
                raise ValueError("La configuración de empresa está incompleta")
            
            logger.info(f"📄 Generando XML con {factura.formas_pago.count()} formas de pago")
            
            # Verificar que el ambiente esté configurado correctamente
            if not emisor.tipo_ambiente or emisor.tipo_ambiente not in ['1', '2']:
                logger.warning(f"Ambiente no válido: {emisor.tipo_ambiente}. Usando '1' (pruebas) por defecto.")
                emisor.tipo_ambiente = '1'
            
            logger.info(f"Emisor: {emisor.razon_social} - RUC: {emisor.identificacion}")
            logger.info(f"Ambiente: {emisor.tipo_ambiente} ({'PRUEBAS' if emisor.tipo_ambiente == '1' else 'PRODUCCIÓN'})")
            
            # Verificar que la factura está lista (si el método existe)
            if hasattr(factura, 'esta_lista_para_xml'):
                lista, errores = factura.esta_lista_para_xml()
                if not lista:
                    raise ValueError(f"Factura no está lista para XML: {', '.join(errores)}")
            else:
                # Validaciones mínimas si el método no existe
                if not factura.cliente:
                    raise ValueError("La factura debe tener un cliente asignado")
                if not hasattr(factura, 'detallefactura_set') or not factura.detallefactura_set.exists():
                    raise ValueError("La factura debe tener al menos un detalle")
                # Verificar configuración del emisor (solo validación manual)
                if (getattr(emisor, 'identificacion', '0000000000000') == '0000000000000' or 
                    '[CONFIGURAR' in getattr(emisor, 'razon_social', '') or
                    '[CONFIGURAR' in getattr(emisor, 'direccion_establecimiento', '') or
                    getattr(emisor, 'correo', 'configurar@empresa.com') == 'configurar@empresa.com' or
                    getattr(emisor, 'telefono', '0000000000') == '0000000000'):
                    raise ValueError("La configuración de empresa está incompleta")
            
            # Crear elemento raíz
            root = ET.Element('factura', {
                'id': 'comprobante',
                'version': '1.1.0'
            })
            
            # 1. Información Tributaria
            self._agregar_info_tributaria(root, factura, emisor)
            
            # 2. Información de la Factura
            self._agregar_info_factura(root, factura, emisor)
            
            # 3. Detalles de la Factura
            self._agregar_detalles_factura(root, factura)
            
            # 4. Información Adicional
            self._agregar_info_adicional(root, factura, emisor)
            
            # Convertir a string con formato
            xml_string = self._formatear_xml(root)
            
            logger.info(f"XML de factura {factura.id} generado exitosamente")
            return xml_string
            
        except Exception as e:
            logger.error(f"Error generando XML de factura {factura.id}: {e}")
            raise

    def _agregar_info_tributaria(self, root, factura, emisor):
        """Agregar información tributaria según ficha técnica SRI"""
        info_tributaria = ET.SubElement(root, 'infoTributaria')
        
        # Campos obligatorios según ficha técnica
        ET.SubElement(info_tributaria, 'ambiente').text = emisor.tipo_ambiente
        ET.SubElement(info_tributaria, 'tipoEmision').text = emisor.tipo_emision
        ET.SubElement(info_tributaria, 'razonSocial').text = self._limpiar_texto(emisor.razon_social)
        
        # Nombre comercial (opcional)
        if emisor.nombre_comercial:
            ET.SubElement(info_tributaria, 'nombreComercial').text = self._limpiar_texto(emisor.nombre_comercial)
        
        # RUC formateado
        if hasattr(emisor, 'ruc_formatted'):
            ruc = emisor.ruc_formatted
        else:
            # Formatear RUC a 13 dígitos
            ruc = str(emisor.identificacion).zfill(13)
            
        ET.SubElement(info_tributaria, 'ruc').text = ruc
        
        # Clave de acceso - USAR LA QUE YA ESTÁ EN EL MODELO
        if not factura.clave_acceso:
            raise ValueError(f"Factura {factura.id} no tiene clave de acceso generada")
        ET.SubElement(info_tributaria, 'claveAcceso').text = factura.clave_acceso
        
        ET.SubElement(info_tributaria, 'codDoc').text = '01'  # Factura
        
        # Formatear establecimiento, punto emisión y secuencial
        # Si las properties no existen, formatear manualmente
        if hasattr(factura, 'establecimiento_formatted'):
            estab = factura.establecimiento_formatted
        else:
            estab = f"{int(factura.establecimiento):03d}"
            
        if hasattr(factura, 'punto_emision_formatted'):
            pto_emi = factura.punto_emision_formatted
        else:
            pto_emi = f"{int(factura.punto_emision):03d}"
            
        if hasattr(factura, 'secuencia_formatted'):
            secuencial = factura.secuencia_formatted
        else:
            secuencial = f"{int(factura.secuencia):09d}"
        
        ET.SubElement(info_tributaria, 'estab').text = estab
        ET.SubElement(info_tributaria, 'ptoEmi').text = pto_emi
        ET.SubElement(info_tributaria, 'secuencial').text = secuencial
        
        # NOTA: direccion_establecimiento es un campo directo, no una propiedad
        direccion_matriz = getattr(emisor, 'direccion_establecimiento', '')
        ET.SubElement(info_tributaria, 'dirMatriz').text = self._limpiar_texto(direccion_matriz)
        
        # Agente de retención (opcional)
        if hasattr(emisor, 'agente_retencion_xml'):
            agente_retencion = emisor.agente_retencion_xml
        else:
            agente_retencion = emisor.numero_agente_retencion if emisor.es_agente_retencion else None
            
        if agente_retencion:
            ET.SubElement(info_tributaria, 'agenteRetencion').text = agente_retencion
        
        # Contribuyente RIMPE (opcional)
        if emisor.tipo_regimen == 'RIMPE':
            ET.SubElement(info_tributaria, 'contribuyenteRimpe').text = 'CONTRIBUYENTE RÉGIMEN RIMPE'

    def _agregar_info_factura(self, root, factura, emisor):
        """Agregar información específica de la factura"""
        info_factura = ET.SubElement(root, 'infoFactura')
        
        # Fecha de emisión
        ET.SubElement(info_factura, 'fechaEmision').text = self._formatear_fecha(factura.fecha_emision)
        
        # Dirección del establecimiento (OBLIGATORIO cuando corresponda)
        # NOTA: direccion_establecimiento es un campo, no una propiedad
        direccion = getattr(emisor, 'direccion_establecimiento', None)
        if direccion:
            ET.SubElement(info_factura, 'dirEstablecimiento').text = self._limpiar_texto(direccion)
        
        # Contribuyente especial (OBLIGATORIO cuando corresponda)
        if hasattr(emisor, 'contribuyente_especial_xml'):
            contribuyente_especial = emisor.contribuyente_especial_xml
        else:
            contribuyente_especial = emisor.numero_contribuyente_especial if emisor.es_contribuyente_especial else None
            
        if contribuyente_especial:
            ET.SubElement(info_factura, 'contribuyenteEspecial').text = contribuyente_especial
        
        # Obligado a llevar contabilidad (OBLIGATORIO cuando corresponda)
        if hasattr(emisor, 'obligado_contabilidad_xml'):
            obligado_contabilidad = emisor.obligado_contabilidad_xml
        else:
            obligado_contabilidad = emisor.obligado
            
        if obligado_contabilidad:
            ET.SubElement(info_factura, 'obligadoContabilidad').text = obligado_contabilidad
        
        # Guía de remisión (opcional)
        if factura.guia_remision:
            ET.SubElement(info_factura, 'guiaRemision').text = factura.guia_remision
        
        # Información del comprador - usar properties si existen, sino valores directos
        if hasattr(factura, 'tipo_identificacion_comprador_xml'):
            tipo_id_comprador = factura.tipo_identificacion_comprador_xml
        else:
            tipo_id_comprador = factura.cliente.tipoIdentificacion if factura.cliente else '07'
            
        if hasattr(factura, 'razon_social_comprador_xml'):
            razon_social_comprador = factura.razon_social_comprador_xml
        else:
            razon_social_comprador = factura.cliente.razon_social if factura.cliente else factura.nombre_cliente
            
        if hasattr(factura, 'direccion_comprador_xml'):
            direccion_comprador = factura.direccion_comprador_xml
        else:
            direccion_comprador = factura.cliente.direccion if factura.cliente else ''
            
        ET.SubElement(info_factura, 'tipoIdentificacionComprador').text = tipo_id_comprador
        ET.SubElement(info_factura, 'razonSocialComprador').text = self._limpiar_texto(razon_social_comprador)
        ET.SubElement(info_factura, 'identificacionComprador').text = factura.identificacion_cliente
        
        # Dirección del comprador (opcional pero requerida para facturas negociables)
        if direccion_comprador:
            ET.SubElement(info_factura, 'direccionComprador').text = self._limpiar_texto(direccion_comprador)
        
        # Totales - usar properties si existen, sino campos directos
        if hasattr(factura, 'total_sin_impuestos_xml'):
            total_sin_impuestos = factura.total_sin_impuestos_xml
        else:
            total_sin_impuestos = factura.sub_monto
            
        ET.SubElement(info_factura, 'totalSinImpuestos').text = self._formatear_decimal(total_sin_impuestos)
        
        # Total subsidio (opcional)
        if factura.total_subsidio > 0:
            ET.SubElement(info_factura, 'totalSubsidio').text = self._formatear_decimal(factura.total_subsidio)
        
        ET.SubElement(info_factura, 'totalDescuento').text = self._formatear_decimal(factura.total_descuento)
        
        # Total con impuestos - LEER DE RELACIÓN totales_impuestos
        total_con_impuestos = ET.SubElement(info_factura, 'totalConImpuestos')
        for total_imp in factura.totales_impuestos.all():
            self._agregar_total_impuesto(total_con_impuestos, total_imp)
        
        # Propina (OBLIGATORIO según ficha técnica)
        ET.SubElement(info_factura, 'propina').text = self._formatear_decimal(factura.propina)
        
        # Importe total
        if hasattr(factura, 'importe_total_xml'):
            importe_total = factura.importe_total_xml
        else:
            importe_total = factura.monto_general
            
        ET.SubElement(info_factura, 'importeTotal').text = self._formatear_decimal(importe_total)
        
        # Moneda
        if hasattr(factura, 'moneda_xml'):
            moneda = factura.moneda_xml
        else:
            moneda = 'DOLAR'
            
        ET.SubElement(info_factura, 'moneda').text = moneda
        
        # Placa (opcional, obligatorio para combustibles)
        if factura.placa:
            ET.SubElement(info_factura, 'placa').text = factura.placa
        
        # 🔍 VALIDACIÓN CRÍTICA SRI: Verificar coherencia entre pagos y total de factura
        if factura.formas_pago.exists():
            logger.info("🔍 Validando coherencia entre pagos y total para XML SRI...")
            
            # Calcular suma total de las formas de pago
            from decimal import Decimal
            suma_pagos = Decimal('0.00')
            formas_pago_list = list(factura.formas_pago.all())
            
            for forma_pago in formas_pago_list:
                suma_pagos += forma_pago.total
                logger.debug(f"Pago: ${forma_pago.total} (Código: {forma_pago.forma_pago})")
            
            # Obtener total de la factura
            total_factura = factura.monto_general
            
            logger.info(f"📊 Total factura: ${total_factura}")
            logger.info(f"📊 Suma pagos: ${suma_pagos}")
            
            # 🚫 VALIDACIÓN ESTRICTA: SIN TOLERANCIA - IGUALDAD EXACTA REQUERIDA
            if total_factura != suma_pagos:
                # RECHAZAR CUALQUIER DISCREPANCIA - XML SRI REQUIERE COHERENCIA PERFECTA
                diferencia = abs(total_factura - suma_pagos)
                error_msg = (
                    f"INCOHERENCIA CRÍTICA EN XML SRI: Total factura (${total_factura}) ≠ Suma pagos (${suma_pagos}). "
                    f"Diferencia: ${diferencia}. SRI REQUIERE IGUALDAD EXACTA - NO se generará XML hasta corregir"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                logger.info(f"✅ Coherencia SRI PERFECTA: Total ${total_factura} = Suma pagos ${suma_pagos}")
        
        # Pagos - LEER DE RELACIÓN formas_pago
        if factura.formas_pago.exists():
            pagos = ET.SubElement(info_factura, 'pagos')
            for forma_pago in factura.formas_pago.all():
                pago = ET.SubElement(pagos, 'pago')
                ET.SubElement(pago, 'formaPago').text = forma_pago.forma_pago
                ET.SubElement(pago, 'total').text = self._formatear_decimal(forma_pago.total)
                
                # Plazo y unidad de tiempo (opcionales)
                if forma_pago.plazo:
                    ET.SubElement(pago, 'plazo').text = self._formatear_decimal(forma_pago.plazo)
                    if forma_pago.unidad_tiempo:
                        ET.SubElement(pago, 'unidadTiempo').text = forma_pago.unidad_tiempo
        
        # Valores de retención (opcionales)
        if factura.valor_retencion_iva > 0:
            ET.SubElement(info_factura, 'valorRetIva').text = self._formatear_decimal(factura.valor_retencion_iva)
        
        if factura.valor_retencion_renta > 0:
            ET.SubElement(info_factura, 'valorRetRenta').text = self._formatear_decimal(factura.valor_retencion_renta)

    def _agregar_total_impuesto(self, total_con_impuestos, total_imp):
        """Agregar un total de impuesto al XML"""
        total_impuesto = ET.SubElement(total_con_impuestos, 'totalImpuesto')
        
        ET.SubElement(total_impuesto, 'codigo').text = total_imp.codigo
        ET.SubElement(total_impuesto, 'codigoPorcentaje').text = total_imp.codigo_porcentaje
        
        # Descuento adicional (solo para IVA)
        if total_imp.codigo == '2' and total_imp.descuento_adicional > 0:
            ET.SubElement(total_impuesto, 'descuentoAdicional').text = self._formatear_decimal(
                total_imp.descuento_adicional
            )
        
        ET.SubElement(total_impuesto, 'baseImponible').text = self._formatear_decimal(total_imp.base_imponible)
        
        # Tarifa (opcional según XSD pero recomendable)
        if total_imp.tarifa:
            ET.SubElement(total_impuesto, 'tarifa').text = self._formatear_decimal(total_imp.tarifa, 0)
        
        ET.SubElement(total_impuesto, 'valor').text = self._formatear_decimal(total_imp.valor)

    def _agregar_detalles_factura(self, root, factura):
        """Agregar detalles de productos/servicios"""
        detalles_element = ET.SubElement(root, 'detalles')
        
        # Prefetch related para optimizar queries
        detalles = factura.detallefactura_set.prefetch_related(
            'producto',
            'impuestos_detalle',
            'detalles_adicionales'
        )
        
        for detalle in detalles:
            detalle_element = ET.SubElement(detalles_element, 'detalle')
            
            # Códigos del producto/servicio - usar properties si existen, sino acceso directo
            if hasattr(detalle, 'codigo_principal_xml'):
                codigo_principal = detalle.codigo_principal_xml
            else:
                if detalle.producto:
                    codigo_principal = detalle.producto.codigo
                elif detalle.servicio:
                    codigo_principal = detalle.servicio.codigo
                else:
                    codigo_principal = ''
                
            if codigo_principal:
                ET.SubElement(detalle_element, 'codigoPrincipal').text = codigo_principal
            
            # Código auxiliar (solo para productos)
            if hasattr(detalle, 'codigo_auxiliar_xml'):
                codigo_auxiliar = detalle.codigo_auxiliar_xml
            else:
                codigo_auxiliar = detalle.producto.codigo_barras if detalle.producto else ''
                
            if codigo_auxiliar:
                ET.SubElement(detalle_element, 'codigoAuxiliar').text = codigo_auxiliar
            
            # Descripción
            if hasattr(detalle, 'descripcion_xml'):
                descripcion = detalle.descripcion_xml
            else:
                if detalle.producto:
                    descripcion = detalle.producto.descripcion
                elif detalle.servicio:
                    descripcion = detalle.servicio.descripcion
                else:
                    descripcion = ''
            ET.SubElement(detalle_element, 'descripcion').text = self._limpiar_texto(descripcion)

            # UNIDAD DE MEDIDA (nuevo)
            unidad = 'unidad'
            if detalle.producto:
                # Mapear la categoría a texto SRI
                categoria_valor = getattr(detalle.producto, 'categoria', None)
                # Opciones del modelo Producto
                categoria_map = {
                    '1': 'unidad',
                    '2': 'kilo',
                    '3': 'litro',
                    '4': 'otros'
                }
                unidad = categoria_map.get(str(categoria_valor), 'unidad')
            elif detalle.servicio:
                # Para servicios, usar 'unidad' por defecto
                unidad = 'unidad'
            ET.SubElement(detalle_element, 'unidadMedida').text = unidad
            
            # Cantidad y precios
            ET.SubElement(detalle_element, 'cantidad').text = self._formatear_decimal(detalle.cantidad)
            
            if hasattr(detalle, 'precio_unitario_xml'):
                precio_unitario = detalle.precio_unitario_xml
            else:
                if detalle.producto:
                    precio_unitario = detalle.producto.precio
                elif detalle.servicio:
                    precio_unitario = detalle.servicio.precio1
                else:
                    precio_unitario = Decimal('0.00')
                
            ET.SubElement(detalle_element, 'precioUnitario').text = self._formatear_decimal(precio_unitario)
            
            # Precio sin subsidio (opcional)
            if detalle.precio_sin_subsidio:
                ET.SubElement(detalle_element, 'precioSinSubsidio').text = self._formatear_decimal(
                    detalle.precio_sin_subsidio
                )
            
            # Descuento (OBLIGATORIO)
            ET.SubElement(detalle_element, 'descuento').text = self._formatear_decimal(detalle.descuento)
            
            # Precio total sin impuesto
            if hasattr(detalle, 'precio_total_sin_impuesto_xml'):
                precio_total_sin_impuesto = detalle.precio_total_sin_impuesto_xml
            else:
                precio_total_sin_impuesto = detalle.sub_total
                
            ET.SubElement(detalle_element, 'precioTotalSinImpuesto').text = self._formatear_decimal(
                precio_total_sin_impuesto
            )
            
            # Detalles adicionales (máximo 3)
            if detalle.detalles_adicionales.exists():
                detalles_adic = ET.SubElement(detalle_element, 'detallesAdicionales')
                for det_adic in detalle.detalles_adicionales.all()[:3]:  # Máximo 3
                    det_adic_elem = ET.SubElement(detalles_adic, 'detAdicional')
                    det_adic_elem.set('nombre', self._limpiar_texto(det_adic.nombre))
                    det_adic_elem.set('valor', self._limpiar_texto(det_adic.valor))
            
            # Impuestos del detalle - LEER DE RELACIÓN impuestos_detalle
            impuestos = ET.SubElement(detalle_element, 'impuestos')
            for imp_det in detalle.impuestos_detalle.all():
                self._agregar_impuesto_detalle(impuestos, imp_det)

    def _agregar_impuesto_detalle(self, impuestos_element, imp_det):
        """Agregar impuesto de un detalle"""
        impuesto = ET.SubElement(impuestos_element, 'impuesto')
        
        ET.SubElement(impuesto, 'codigo').text = imp_det.codigo
        ET.SubElement(impuesto, 'codigoPorcentaje').text = imp_det.codigo_porcentaje
        ET.SubElement(impuesto, 'tarifa').text = self._formatear_decimal(imp_det.tarifa)
        ET.SubElement(impuesto, 'baseImponible').text = self._formatear_decimal(imp_det.base_imponible)
        ET.SubElement(impuesto, 'valor').text = self._formatear_decimal(imp_det.valor)

    def _agregar_info_adicional(self, root, factura, emisor):
        """Agregar información adicional"""
        # Solo agregar si hay campos adicionales
        campos_adicionales = list(factura.campos_adicionales.all())
        
        # Agregar datos del emisor si no están en campos adicionales
        nombres_existentes = [campo.nombre.upper() for campo in campos_adicionales]
        
        # Auto-agregar email si no existe
        if emisor.correo and 'E-MAIL' not in nombres_existentes:
            from inventario.models import CampoAdicional
            campo_email = CampoAdicional(nombre='E-MAIL', valor=emisor.correo)
            campos_adicionales.append(campo_email)
        
        # Auto-agregar teléfono si no existe
        if emisor.telefono and 'TELÉFONO' not in nombres_existentes:
            from inventario.models import CampoAdicional
            campo_telefono = CampoAdicional(nombre='TELÉFONO', valor=emisor.telefono)
            campos_adicionales.append(campo_telefono)
        
        # Auto-agregar dirección si no existe
        direccion_emisor = getattr(emisor, 'direccion_establecimiento', None)
        if direccion_emisor and 'DIRECCIÓN' not in nombres_existentes:
            from inventario.models import CampoAdicional
            campo_direccion = CampoAdicional(
                nombre='DIRECCIÓN', 
                valor=self._limpiar_texto(direccion_emisor)
            )
            campos_adicionales.append(campo_direccion)
        
        # Si hay campos adicionales, crear la sección
        if campos_adicionales:
            info_adicional = ET.SubElement(root, 'infoAdicional')
            
            # Máximo 15 campos según XSD
            for campo in campos_adicionales[:15]:
                campo_elem = ET.SubElement(info_adicional, 'campoAdicional')
                campo_elem.set('nombre', campo.nombre)
                campo_elem.text = self._limpiar_texto(campo.valor)
        
        # Tipo negociable (solo si existe)
        if hasattr(factura, 'tipo_negociable'):
            self._agregar_tipo_negociable(root, factura.tipo_negociable)
        
        # Máquina fiscal (solo si existe)
        if hasattr(factura, 'maquina_fiscal'):
            self._agregar_maquina_fiscal(root, factura.maquina_fiscal)

    def _agregar_tipo_negociable(self, root, tipo_negociable):
        """Agregar información de factura comercial negociable"""
        # Insertar antes de infoAdicional
        info_adicional = root.find('infoAdicional')
        if info_adicional is not None:
            indice = list(root).index(info_adicional)
        else:
            indice = len(list(root))
        
        tipo_neg_elem = ET.Element('tipoNegociable')
        ET.SubElement(tipo_neg_elem, 'correo').text = tipo_negociable.correo
        
        root.insert(indice, tipo_neg_elem)

    def _agregar_maquina_fiscal(self, root, maquina_fiscal):
        """Agregar información de máquina fiscal"""
        # Insertar antes de infoAdicional
        info_adicional = root.find('infoAdicional')
        if info_adicional is not None:
            indice = list(root).index(info_adicional)
        else:
            indice = len(list(root))
        
        maq_fiscal_elem = ET.Element('maquinaFiscal')
        ET.SubElement(maq_fiscal_elem, 'marca').text = self._limpiar_texto(maquina_fiscal.marca)
        ET.SubElement(maq_fiscal_elem, 'modelo').text = self._limpiar_texto(maquina_fiscal.modelo)
        ET.SubElement(maq_fiscal_elem, 'serie').text = self._limpiar_texto(maquina_fiscal.serie)
        
        root.insert(indice, maq_fiscal_elem)

    def _formatear_xml(self, root):
        """Formatear XML con indentación bonita"""
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        
        # Obtener el XML formateado
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')
        
        # Limpiar líneas vacías extra
        lines = [line for line in pretty_xml.split('\n') if line.strip()]
        
        # Asegurar que la declaración XML esté en la primera línea
        if lines[0].startswith('<?xml'):
            return '\n'.join(lines)
        else:
            return '<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines)
