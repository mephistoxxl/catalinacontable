"""
Generador de XML para Liquidaciones de Compra (codDoc 03)
Basado en la ficha técnica del SRI Ecuador v2.31
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from decimal import Decimal
from collections import defaultdict
import logging
import os
from lxml import etree

logger = logging.getLogger(__name__)


class LiquidacionXMLGenerator:
    """Generador de XML específico para Liquidaciones de Compra electrónicas."""

    def validar_xml_contra_xsd(self, xml_content, xsd_path):
        """
        Valida el XML contra el XSD oficial del SRI para liquidaciones.
        
        Args:
            xml_content (str): Contenido XML a validar
            xsd_path (str): Ruta al archivo XSD de liquidación
            
        Returns:
            dict: {
                'valido': bool,
                'mensaje': str,
                'errores': str (si hay errores)
            }
        """
        try:
            if not os.path.exists(xsd_path):
                raise FileNotFoundError(f"Archivo XSD no encontrado: {xsd_path}")
            
            # Cargar esquemas dependientes (xmldsig)
            sri_dir = os.path.dirname(xsd_path)
            xmldsig_path = os.path.join(sri_dir, 'xmldsig-core-schema.xsd')
            
            # Parsear XML
            xml_doc = etree.fromstring(xml_content.encode('utf-8'))
            
            # Cargar y parsear XSD
            with open(xsd_path, 'rb') as xsd_file:
                xsd_doc = etree.parse(xsd_file)
                schema = etree.XMLSchema(xsd_doc)
            
            # Validar
            if schema.validate(xml_doc):
                return {
                    'valido': True,
                    'mensaje': 'XML válido según XSD del SRI'
                }
            else:
                errores = '\n'.join([str(e) for e in schema.error_log])
                return {
                    'valido': False,
                    'mensaje': 'El XML no cumple con el esquema XSD',
                    'errores': errores
                }
                
        except FileNotFoundError as e:
            return {
                'valido': False,
                'mensaje': str(e),
                'errores': 'Archivo XSD no encontrado'
            }
        except etree.XMLSyntaxError as e:
            return {
                'valido': False,
                'mensaje': 'Error de sintaxis en el XML',
                'errores': str(e)
            }
        except Exception as e:
            logger.error(f"Error validando XML: {e}")
            return {
                'valido': False,
                'mensaje': f'Error en validación: {str(e)}',
                'errores': str(e)
            }

    def generar_xml_liquidacion(self, liquidacion):
        """
        Genera el XML de una liquidación de compra según el formato del SRI.
        Cumple con Ficha Técnica v2.32, Anexo 17, versión 1.1.0
        
        Args:
            liquidacion: Instancia de LiquidacionCompra
            
        Returns:
            str: XML formateado
        """
        # Crear elemento raíz con namespace para firma digital
        root = ET.Element('liquidacionCompra', {
            'id': 'comprobante',
            'version': '1.1.0'
        })

        # 1. InfoTributaria - OBLIGATORIO
        info_tributaria = ET.SubElement(root, 'infoTributaria')
        
        empresa = liquidacion.empresa
        opciones = empresa.opciones.first() if hasattr(empresa, 'opciones') else None
        
        # ambiente: 1=pruebas, 2=producción - OBLIGATORIO
        ambiente = '1'  # Default: pruebas
        if opciones and opciones.tipo_ambiente in ('1', '2'):
            ambiente = opciones.tipo_ambiente
        ET.SubElement(info_tributaria, 'ambiente').text = ambiente
        
        # tipoEmision: 1=normal, 2=contingencia - OBLIGATORIO
        tipo_emision = '1'  # Default: normal
        if opciones and opciones.tipo_emision in ('1', '2'):
            tipo_emision = opciones.tipo_emision
        ET.SubElement(info_tributaria, 'tipoEmision').text = tipo_emision
        
        # razonSocial del emisor - OBLIGATORIO
        razon_social = opciones.razon_social if opciones and opciones.razon_social else empresa.razon_social
        ET.SubElement(info_tributaria, 'razonSocial').text = razon_social[:300]
        
        # nombreComercial - OPCIONAL
        nombre_comercial = opciones.nombre_comercial if opciones and opciones.nombre_comercial else None
        if nombre_comercial:
            ET.SubElement(info_tributaria, 'nombreComercial').text = nombre_comercial[:300]
        
        # RUC del emisor - OBLIGATORIO (formato: 10 dígitos + 001)
        ruc = opciones.identificacion if opciones and opciones.identificacion else empresa.ruc
        ET.SubElement(info_tributaria, 'ruc').text = ruc
        
        # claveAcceso de 49 dígitos - OBLIGATORIO
        ET.SubElement(info_tributaria, 'claveAcceso').text = liquidacion.clave_acceso
        
        # codDoc: 03 para liquidación de compra - OBLIGATORIO
        ET.SubElement(info_tributaria, 'codDoc').text = '03'
        
        # Establecimiento (3 dígitos) - OBLIGATORIO
        ET.SubElement(info_tributaria, 'estab').text = f"{liquidacion.establecimiento:03d}"
        
        # Punto de emisión (3 dígitos) - OBLIGATORIO
        ET.SubElement(info_tributaria, 'ptoEmi').text = f"{liquidacion.punto_emision:03d}"
        
        # Secuencial (9 dígitos) - OBLIGATORIO
        ET.SubElement(info_tributaria, 'secuencial').text = f"{liquidacion.secuencia:09d}"
        
        # Dirección matriz del emisor - OBLIGATORIO
        dir_matriz = opciones.direccion_establecimiento if opciones and opciones.direccion_establecimiento else 'SIN DIRECCION'
        ET.SubElement(info_tributaria, 'dirMatriz').text = dir_matriz[:300]
        
        # Agente de retención - OPCIONAL (máximo 8 dígitos)
        if opciones and opciones.agente_retencion and opciones.agente_retencion != '...':
            ET.SubElement(info_tributaria, 'agenteRetencion').text = str(opciones.agente_retencion)[:8]
        
        # Contribuyente RIMPE - OPCIONAL (muy raro, omitir si no existe)
        # if opciones and hasattr(opciones, 'contribuyente_rimpe') and opciones.contribuyente_rimpe:
        #     ET.SubElement(info_tributaria, 'contribuyenteRimpe').text = 'CONTRIBUYENTE RÉGIMEN RIMPE'

        # 2. InfoLiquidacionCompra - OBLIGATORIO
        info_liquidacion = ET.SubElement(root, 'infoLiquidacionCompra')
        
        # fechaEmision en formato dd/mm/aaaa - OBLIGATORIO
        ET.SubElement(info_liquidacion, 'fechaEmision').text = liquidacion.fecha_emision.strftime('%d/%m/%Y')
        
        # dirEstablecimiento - OPCIONAL
        if opciones and opciones.direccion_establecimiento:
            ET.SubElement(info_liquidacion, 'dirEstablecimiento').text = opciones.direccion_establecimiento[:300]
        
        # contribuyenteEspecial - OPCIONAL (3-13 caracteres alfanuméricos)
        if opciones and opciones.numero_contribuyente_especial:
            ET.SubElement(info_liquidacion, 'contribuyenteEspecial').text = str(opciones.numero_contribuyente_especial)[:13]
        
        # obligadoContabilidad - OPCIONAL pero recomendado
        obligado_conta = 'SI' if (opciones and opciones.obligado == 'SI') else 'NO'
        ET.SubElement(info_liquidacion, 'obligadoContabilidad').text = obligado_conta
        
        # DATOS DEL PROVEEDOR (quien presta el servicio/vende) - OBLIGATORIOS
        proveedor = liquidacion.proveedor
        
        # tipoIdentificacionProveedor: 04=RUC, 05=Cédula, 06=Pasaporte, 07=Consumidor final, 08=Identificación exterior
        tipo_id = proveedor.tipoIdentificacion if proveedor.tipoIdentificacion else '05'
        ET.SubElement(info_liquidacion, 'tipoIdentificacionProveedor').text = tipo_id
        
        # razonSocialProveedor - OBLIGATORIO (1-300 caracteres)
        razon_social = proveedor.razon_social_proveedor or proveedor.nombre_comercial_proveedor or 'PROVEEDOR'
        ET.SubElement(info_liquidacion, 'razonSocialProveedor').text = razon_social[:300]
        
        # identificacionProveedor - OBLIGATORIO (1-20 caracteres)
        identificacion = proveedor.identificacion_proveedor if proveedor.identificacion_proveedor else '9999999999999'
        ET.SubElement(info_liquidacion, 'identificacionProveedor').text = identificacion[:20]
        
        # direccionProveedor - OPCIONAL
        if proveedor.direccion:
            ET.SubElement(info_liquidacion, 'direccionProveedor').text = proveedor.direccion[:300]
        
        # TOTALES - OBLIGATORIOS
        # totalSinImpuestos (14 dígitos, 2 decimales)
        ET.SubElement(info_liquidacion, 'totalSinImpuestos').text = self._format_decimal(liquidacion.total_sin_impuestos)
        
        # totalDescuento (14 dígitos, 2 decimales)
        ET.SubElement(info_liquidacion, 'totalDescuento').text = self._format_decimal(liquidacion.total_descuento)
        
        # REEMBOLSOS - OPCIONALES (solo si aplica)
        if hasattr(liquidacion, 'codigo_doc_reembolso') and liquidacion.codigo_doc_reembolso:
            ET.SubElement(info_liquidacion, 'codDocReembolso').text = str(liquidacion.codigo_doc_reembolso)
        
        if hasattr(liquidacion, 'total_comprobantes_reembolso') and liquidacion.total_comprobantes_reembolso:
            ET.SubElement(info_liquidacion, 'totalComprobantesReembolso').text = self._format_decimal(liquidacion.total_comprobantes_reembolso)
        
        if hasattr(liquidacion, 'total_base_imponible_reembolso') and liquidacion.total_base_imponible_reembolso:
            ET.SubElement(info_liquidacion, 'totalBaseImponibleReembolso').text = self._format_decimal(liquidacion.total_base_imponible_reembolso)
        
        if hasattr(liquidacion, 'total_impuesto_reembolso') and liquidacion.total_impuesto_reembolso:
            ET.SubElement(info_liquidacion, 'totalImpuestoReembolso').text = self._format_decimal(liquidacion.total_impuesto_reembolso)
        
        # totalConImpuestos - OBLIGATORIO (al menos un totalImpuesto)
        total_con_impuestos = ET.SubElement(info_liquidacion, 'totalConImpuestos')
        
        # Si no existen totales_impuestos, generarlos desde los detalles
        totales_imp = liquidacion.totales_impuestos.all()
        if not totales_imp.exists():
            # Generar totales agrupados por código IVA desde detalles
            totales_imp = self._generar_totales_impuestos_desde_detalles(liquidacion)
        
        for total_imp in totales_imp:
            total_impuesto = ET.SubElement(total_con_impuestos, 'totalImpuesto')
            
            # codigo: siempre 2 para IVA en liquidaciones
            ET.SubElement(total_impuesto, 'codigo').text = total_imp.codigo
            
            # codigoPorcentaje: código de tarifa IVA (0, 2, 3, etc.)
            ET.SubElement(total_impuesto, 'codigoPorcentaje').text = total_imp.codigo_porcentaje
            
            # descuentoAdicional - OPCIONAL
            if total_imp.descuento_adicional and total_imp.descuento_adicional != Decimal('0.00'):
                ET.SubElement(total_impuesto, 'descuentoAdicional').text = self._format_decimal(total_imp.descuento_adicional)
            
            # baseImponible - OBLIGATORIO
            ET.SubElement(total_impuesto, 'baseImponible').text = self._format_decimal(total_imp.base_imponible)
            
            # tarifa - OPCIONAL (porcentaje del impuesto, ej: 15 para IVA 15%)
            if hasattr(total_imp, 'tarifa') and total_imp.tarifa is not None:
                ET.SubElement(total_impuesto, 'tarifa').text = self._format_decimal(total_imp.tarifa, decimales=2)
            
            # valor - OBLIGATORIO (monto del impuesto)
            ET.SubElement(total_impuesto, 'valor').text = self._format_decimal(total_imp.valor)
        
        # importeTotal - OBLIGATORIO
        ET.SubElement(info_liquidacion, 'importeTotal').text = self._format_decimal(liquidacion.importe_total)
        
        # moneda - OPCIONAL (default DOLAR)
        moneda = liquidacion.moneda if hasattr(liquidacion, 'moneda') and liquidacion.moneda else 'DOLAR'
        ET.SubElement(info_liquidacion, 'moneda').text = moneda[:15]
        
        # pagos - OPCIONAL pero recomendado
        if liquidacion.formas_pago.exists():
            pagos = ET.SubElement(info_liquidacion, 'pagos')
            for forma_pago in liquidacion.formas_pago.all():
                pago = ET.SubElement(pagos, 'pago')
                
                # formaPago: 01-21 según catálogo SRI - OBLIGATORIO
                ET.SubElement(pago, 'formaPago').text = forma_pago.forma_pago
                
                # total - OBLIGATORIO
                ET.SubElement(pago, 'total').text = self._format_decimal(forma_pago.total)
                
                # plazo - OPCIONAL (para crédito)
                if forma_pago.plazo:
                    ET.SubElement(pago, 'plazo').text = self._format_decimal(forma_pago.plazo)
                
                # unidadTiempo - OPCIONAL (días, meses, etc.)
                if forma_pago.unidad_tiempo:
                    ET.SubElement(pago, 'unidadTiempo').text = forma_pago.unidad_tiempo[:10]

        # 3. Detalles - OBLIGATORIO (al menos 1 detalle)
        detalles = ET.SubElement(root, 'detalles')
        for detalle in liquidacion.detalles.all():
            detalle_elem = ET.SubElement(detalles, 'detalle')
            
            # codigoPrincipal - OPCIONAL pero recomendado (1-25 caracteres)
            codigo_principal = 'N/A'
            if detalle.producto:
                codigo_principal = detalle.producto.codigo[:25]
            elif detalle.servicio:
                codigo_principal = detalle.servicio.codigo[:25]
            ET.SubElement(detalle_elem, 'codigoPrincipal').text = codigo_principal
            
            # codigoAuxiliar - OPCIONAL (1-25 caracteres)
            if detalle.producto and hasattr(detalle.producto, 'codigo_auxiliar') and detalle.producto.codigo_auxiliar:
                ET.SubElement(detalle_elem, 'codigoAuxiliar').text = detalle.producto.codigo_auxiliar[:25]
            
            # descripcion - OBLIGATORIO (1-300 caracteres)
            ET.SubElement(detalle_elem, 'descripcion').text = detalle.descripcion[:300]
            
            # unidadMedida - OPCIONAL (1-50 caracteres)
            if detalle.unidad_medida:
                ET.SubElement(detalle_elem, 'unidadMedida').text = detalle.unidad_medida[:50]
            
            # cantidad - OBLIGATORIO (18 dígitos, hasta 6 decimales en v1.1.0)
            ET.SubElement(detalle_elem, 'cantidad').text = self._format_decimal(detalle.cantidad, decimales=6)
            
            # precioUnitario - OBLIGATORIO (18 dígitos, hasta 6 decimales en v1.1.0)
            ET.SubElement(detalle_elem, 'precioUnitario').text = self._format_decimal(detalle.costo, decimales=6)
            
            # precioSinSubsidio - OPCIONAL (para artículos subsidiados)
            if hasattr(detalle, 'precio_sin_subsidio') and detalle.precio_sin_subsidio:
                ET.SubElement(detalle_elem, 'precioSinSubsidio').text = self._format_decimal(detalle.precio_sin_subsidio, decimales=6)
            
            # descuento - OBLIGATORIO (14 dígitos, 2 decimales)
            ET.SubElement(detalle_elem, 'descuento').text = self._format_decimal(detalle.descuento)
            
            # precioTotalSinImpuesto - OBLIGATORIO
            ET.SubElement(detalle_elem, 'precioTotalSinImpuesto').text = self._format_decimal(detalle.precio_total_sin_impuesto)
            
            # detallesAdicionales - OPCIONAL (máximo 3 detalles adicionales)
            if hasattr(detalle, 'detalles_adicionales') and detalle.detalles_adicionales:
                detalles_adic = ET.SubElement(detalle_elem, 'detallesAdicionales')
                # Aquí podrías agregar hasta 3 detAdicional con atributos nombre y valor
                # Por ahora lo dejamos vacío, se implementa si es necesario
            
            # impuestos - OBLIGATORIO (al menos 1 impuesto por detalle)
            impuestos = ET.SubElement(detalle_elem, 'impuestos')
            
            # Si no existen impuestos en el detalle, generarlos desde los campos del detalle
            impuestos_detalle = detalle.impuestos.all()
            if not impuestos_detalle.exists():
                impuestos_detalle = self._generar_impuestos_desde_detalle(detalle)
            
            for impuesto in impuestos_detalle:
                impuesto_elem = ET.SubElement(impuestos, 'impuesto')
                
                # codigo: 2=IVA - OBLIGATORIO
                ET.SubElement(impuesto_elem, 'codigo').text = impuesto.codigo
                
                # codigoPorcentaje - OBLIGATORIO (1-4 dígitos)
                ET.SubElement(impuesto_elem, 'codigoPorcentaje').text = impuesto.codigo_porcentaje
                
                # tarifa - OBLIGATORIO (4 dígitos, 2 decimales)
                ET.SubElement(impuesto_elem, 'tarifa').text = self._format_decimal(impuesto.tarifa, decimales=2)
                
                # baseImponible - OBLIGATORIO
                ET.SubElement(impuesto_elem, 'baseImponible').text = self._format_decimal(impuesto.base_imponible)
                
                # valor - OBLIGATORIO (valor del impuesto)
                ET.SubElement(impuesto_elem, 'valor').text = self._format_decimal(impuesto.valor)

        # 4. Reembolsos - OPCIONAL (solo si la liquidación incluye reembolsos)
        if hasattr(liquidacion, 'reembolsos') and liquidacion.reembolsos.exists():
            reembolsos = ET.SubElement(root, 'reembolsos')
            for reembolso in liquidacion.reembolsos.all():
                reembolso_detalle = ET.SubElement(reembolsos, 'reembolsoDetalle')
                ET.SubElement(reembolso_detalle, 'tipoIdentificacionProveedorReembolso').text = reembolso.tipo_identificacion
                ET.SubElement(reembolso_detalle, 'identificacionProveedorReembolso').text = reembolso.identificacion[:20]
                
                if hasattr(reembolso, 'cod_pais_pago') and reembolso.cod_pais_pago:
                    ET.SubElement(reembolso_detalle, 'codPaisPagoProveedorReembolso').text = reembolso.cod_pais_pago
                
                ET.SubElement(reembolso_detalle, 'tipoProveedorReembolso').text = reembolso.tipo_proveedor
                ET.SubElement(reembolso_detalle, 'codDocReembolso').text = reembolso.cod_doc
                ET.SubElement(reembolso_detalle, 'estabDocReembolso').text = f"{reembolso.establecimiento:03d}"
                ET.SubElement(reembolso_detalle, 'ptoEmiDocReembolso').text = f"{reembolso.punto_emision:03d}"
                ET.SubElement(reembolso_detalle, 'secuencialDocReembolso').text = f"{reembolso.secuencial:09d}"
                ET.SubElement(reembolso_detalle, 'fechaEmisionDocReembolso').text = reembolso.fecha_emision.strftime('%d/%m/%Y')
                ET.SubElement(reembolso_detalle, 'numeroautorizacionDocReemb').text = reembolso.numero_autorizacion
                
                detalleImpuestos = ET.SubElement(reembolso_detalle, 'detalleImpuestos')
                for imp_reemb in reembolso.impuestos.all():
                    detalleImpuesto = ET.SubElement(detalleImpuestos, 'detalleImpuesto')
                    ET.SubElement(detalleImpuesto, 'codigo').text = imp_reemb.codigo
                    ET.SubElement(detalleImpuesto, 'codigoPorcentaje').text = imp_reemb.codigo_porcentaje
                    ET.SubElement(detalleImpuesto, 'tarifa').text = self._format_decimal(imp_reemb.tarifa, decimales=2)
                    ET.SubElement(detalleImpuesto, 'baseImponibleReembolso').text = self._format_decimal(imp_reemb.base_imponible)
                    ET.SubElement(detalleImpuesto, 'impuestoReembolso').text = self._format_decimal(imp_reemb.valor)

        # 5. TipoNegociable - OPCIONAL (para documentos negociables electrónicos)
        if hasattr(liquidacion, 'correo_negociable') and liquidacion.correo_negociable:
            tipo_negociable = ET.SubElement(root, 'tipoNegociable')
            ET.SubElement(tipo_negociable, 'correo').text = liquidacion.correo_negociable[:100]

        # 6. MáquinaFiscal - OPCIONAL (para máquinas registradoras)
        if hasattr(liquidacion, 'maquina_fiscal_marca') and liquidacion.maquina_fiscal_marca:
            maquina_fiscal = ET.SubElement(root, 'maquinaFiscal')
            ET.SubElement(maquina_fiscal, 'marca').text = liquidacion.maquina_fiscal_marca[:30]
            ET.SubElement(maquina_fiscal, 'modelo').text = liquidacion.maquina_fiscal_modelo[:30]
            ET.SubElement(maquina_fiscal, 'serie').text = liquidacion.maquina_fiscal_serie[:30]

        # 7. Información adicional - OPCIONAL (máximo 15 campos adicionales)
        campos_adicionales = liquidacion.campos_adicionales.all()
        if campos_adicionales.exists() or liquidacion.observaciones:
            info_adicional = ET.SubElement(root, 'infoAdicional')
            
            # Agregar observaciones como campo adicional
            if liquidacion.observaciones:
                campo = ET.SubElement(info_adicional, 'campoAdicional', nombre='Observaciones')
                campo.text = liquidacion.observaciones[:300]  # Límite de 300 caracteres
            
            # Agregar campos adicionales definidos (máximo 15)
            for campo_adicional in campos_adicionales[:15]:
                campo = ET.SubElement(info_adicional, 'campoAdicional', nombre=campo_adicional.nombre[:300])
                campo.text = campo_adicional.valor[:300]

        # Convertir a string con formato
        return self._prettify_xml(root)

    def _generar_totales_impuestos_desde_detalles(self, liquidacion):
        """Genera totales de impuestos agrupados por código desde los detalles."""
        from collections import defaultdict
        totales = defaultdict(lambda: {'base': Decimal('0.00'), 'valor': Decimal('0.00'), 'tarifa': None})
        
        for detalle in liquidacion.detalles.all():
            codigo_iva = detalle.codigo_iva or '2'
            totales[codigo_iva]['base'] += detalle.precio_total_sin_impuesto
            totales[codigo_iva]['valor'] += detalle.valor_iva
            if totales[codigo_iva]['tarifa'] is None:
                totales[codigo_iva]['tarifa'] = detalle.tarifa_iva
        
        # Crear objetos simulados para el XML
        class TotalImpuestoSimulado:
            def __init__(self, codigo_porc, base, valor, tarifa):
                self.codigo = '2'  # Siempre IVA
                self.codigo_porcentaje = codigo_porc
                self.base_imponible = base
                self.valor = valor
                self.tarifa = tarifa
                self.descuento_adicional = Decimal('0.00')
        
        return [TotalImpuestoSimulado(cod, data['base'], data['valor'], data['tarifa']) 
                for cod, data in totales.items()]
    
    def _generar_impuestos_desde_detalle(self, detalle):
        """Genera impuesto del detalle desde sus campos."""
        class ImpuestoSimulado:
            def __init__(self, detalle):
                self.codigo = '2'  # IVA
                self.codigo_porcentaje = detalle.codigo_iva or '2'
                self.tarifa = detalle.tarifa_iva * Decimal('100')  # Convertir 0.15 a 15
                self.base_imponible = detalle.precio_total_sin_impuesto
                self.valor = detalle.valor_iva
        
        return [ImpuestoSimulado(detalle)]
    
    def _format_decimal(self, valor, decimales=2):
        """Formatea un valor decimal según los estándares del SRI."""
        if valor is None:
            valor = Decimal('0.00')
        elif not isinstance(valor, Decimal):
            valor = Decimal(str(valor))
        
        # Redondear a los decimales especificados
        formato = f"{{:.{decimales}f}}"
        return formato.format(valor)

    def _prettify_xml(self, elem):
        """Convierte el elemento XML en un string formateado."""
        rough_string = ET.tostring(elem, encoding='utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding='UTF-8')
        
        # Eliminar líneas vacías
        lines = [line for line in pretty_xml.decode('utf-8').split('\n') if line.strip()]
        return '\n'.join(lines)

    def guardar_xml(self, liquidacion, ruta_destino):
        """
        Genera y guarda el XML de la liquidación en el sistema de archivos.
        
        Args:
            liquidacion: Instancia de LiquidacionCompra
            ruta_destino: Ruta donde guardar el archivo XML
            
        Returns:
            str: Ruta del archivo guardado
        """
        xml_content = self.generar_xml_liquidacion(liquidacion)
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
        
        # Guardar archivo
        with open(ruta_destino, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        logger.info(f"XML de liquidación guardado en: {ruta_destino}")
        return ruta_destino
