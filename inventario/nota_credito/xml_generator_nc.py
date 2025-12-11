"""
Generador de XML para Notas de Crédito Electrónicas
Según especificación técnica del SRI - codDoc: 04
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class XMLGeneratorNotaCredito:
    """
    Genera el XML de Nota de Crédito según el formato del SRI
    """
    
    VERSION_XML = '1.0'
    ENCODING = 'UTF-8'
    VERSION_NC = '1.1.0'
    
    def __init__(self, nota_credito, opciones=None):
        """
        Args:
            nota_credito: Instancia de NotaCredito
            opciones: Instancia de Opciones (configuración de la empresa)
        """
        self.nc = nota_credito
        self.opciones = opciones
        self.empresa = nota_credito.empresa
    
    def generar_xml(self):
        """Genera el XML completo de la Nota de Crédito"""
        
        # Elemento raíz
        root = ET.Element('notaCredito')
        root.set('id', 'comprobante')
        root.set('version', self.VERSION_NC)
        
        # Agregar secciones
        self._agregar_info_tributaria(root)
        self._agregar_info_nota_credito(root)
        self._agregar_detalles(root)
        self._agregar_info_adicional(root)
        
        # Convertir a string formateado
        xml_string = ET.tostring(root, encoding='unicode')
        
        # Agregar declaración XML
        xml_declaration = f'<?xml version="{self.VERSION_XML}" encoding="{self.ENCODING}"?>'
        xml_completo = xml_declaration + xml_string
        
        return xml_completo
    
    def _agregar_info_tributaria(self, root):
        """Agrega el bloque infoTributaria según XSD v1.1.0"""
        info_trib = ET.SubElement(root, 'infoTributaria')
        
        # Ambiente (1=Pruebas, 2=Producción)
        ambiente = '1' if self.opciones and self.opciones.tipo_ambiente == '1' else '2'
        ET.SubElement(info_trib, 'ambiente').text = ambiente
        
        # Tipo de emisión (1=Normal)
        ET.SubElement(info_trib, 'tipoEmision').text = '1'
        
        # Razón social
        ET.SubElement(info_trib, 'razonSocial').text = self._limpiar_texto(
            self.opciones.razon_social if self.opciones else self.empresa.razon_social
        )
        
        # Nombre comercial (opcional)
        nombre_comercial = self.opciones.nombre_comercial if self.opciones and self.opciones.nombre_comercial else ''
        if nombre_comercial:
            ET.SubElement(info_trib, 'nombreComercial').text = self._limpiar_texto(nombre_comercial)
        
        # RUC
        ET.SubElement(info_trib, 'ruc').text = self.empresa.ruc
        
        # Clave de acceso
        if self.nc.clave_acceso:
            ET.SubElement(info_trib, 'claveAcceso').text = self.nc.clave_acceso
        
        # Código del documento (04 = Nota de Crédito)
        ET.SubElement(info_trib, 'codDoc').text = '04'
        
        # Establecimiento
        ET.SubElement(info_trib, 'estab').text = self.nc.establecimiento
        
        # Punto de emisión
        ET.SubElement(info_trib, 'ptoEmi').text = self.nc.punto_emision
        
        # Secuencial
        ET.SubElement(info_trib, 'secuencial').text = self.nc.secuencial
        
        # Dirección matriz
        direccion = self.opciones.direccion_establecimiento if self.opciones else 'S/N'
        ET.SubElement(info_trib, 'dirMatriz').text = self._limpiar_texto(direccion)
        
        # Agente de retención (opcional)
        if self.opciones and hasattr(self.opciones, 'agente_retencion') and self.opciones.agente_retencion:
            ET.SubElement(info_trib, 'agenteRetencion').text = self.opciones.agente_retencion
        
        # Contribuyente RIMPE (opcional)
        if self.opciones and hasattr(self.opciones, 'contribuyente_rimpe') and self.opciones.contribuyente_rimpe:
            ET.SubElement(info_trib, 'contribuyenteRimpe').text = 'CONTRIBUYENTE RÉGIMEN RIMPE'
    
    def _agregar_info_nota_credito(self, root):
        """Agrega el bloque infoNotaCredito según orden XSD v1.1.0"""
        info_nc = ET.SubElement(root, 'infoNotaCredito')
        
        # 1. Fecha de emisión (requerido)
        fecha_emision = self.nc.fecha_emision.strftime('%d/%m/%Y')
        ET.SubElement(info_nc, 'fechaEmision').text = fecha_emision
        
        # 2. Dirección establecimiento (opcional)
        direccion = self.opciones.direccion_establecimiento if self.opciones else 'S/N'
        if direccion:
            ET.SubElement(info_nc, 'dirEstablecimiento').text = self._limpiar_texto(direccion)
        
        # 3. Tipo de identificación del comprador (requerido)
        factura = self.nc.factura_modificada
        cliente = factura.cliente
        tipo_id = cliente.tipoIdentificacion if cliente else '05'
        ET.SubElement(info_nc, 'tipoIdentificacionComprador').text = tipo_id
        
        # 4. Razón social del comprador (requerido)
        razon_social_comprador = cliente.razon_social if cliente else factura.nombre_cliente
        ET.SubElement(info_nc, 'razonSocialComprador').text = self._limpiar_texto(razon_social_comprador)
        
        # 5. Identificación del comprador (requerido)
        identificacion = cliente.cedula if cliente else factura.identificacion_cliente
        ET.SubElement(info_nc, 'identificacionComprador').text = identificacion
        
        # 6. Contribuyente especial (opcional)
        if self.opciones and self.opciones.numero_contribuyente_especial:
            ET.SubElement(info_nc, 'contribuyenteEspecial').text = self.opciones.numero_contribuyente_especial
        
        # 7. Obligado a llevar contabilidad (opcional)
        obligado = 'SI' if self.opciones and self.opciones.obligado else 'NO'
        ET.SubElement(info_nc, 'obligadoContabilidad').text = obligado
        
        # 8. RISE (opcional) - No implementado generalmente
        # if self.opciones and hasattr(self.opciones, 'rise') and self.opciones.rise:
        #     ET.SubElement(info_nc, 'rise').text = self.opciones.rise
        
        # 9. Código del documento modificado (requerido) - 01=Factura
        ET.SubElement(info_nc, 'codDocModificado').text = self.nc.cod_doc_modificado
        
        # 10. Número del documento modificado (requerido)
        ET.SubElement(info_nc, 'numDocModificado').text = self.nc.num_doc_modificado
        
        # 11. Fecha de emisión del documento sustento (requerido)
        fecha_sustento = self.nc.fecha_emision_doc_sustento.strftime('%d/%m/%Y')
        ET.SubElement(info_nc, 'fechaEmisionDocSustento').text = fecha_sustento
        
        # 12. Total sin impuestos (requerido)
        ET.SubElement(info_nc, 'totalSinImpuestos').text = self._formatear_decimal(
            self.nc.subtotal_sin_impuestos
        )
        
        # 13. Compensaciones (opcional) - No implementado
        # self._agregar_compensaciones(info_nc)
        
        # 14. Valor modificación (requerido) - Total de la NC
        ET.SubElement(info_nc, 'valorModificacion').text = self._formatear_decimal(
            self.nc.valor_modificacion
        )
        
        # 15. Moneda (opcional)
        ET.SubElement(info_nc, 'moneda').text = 'DOLAR'
        
        # 16. Total con impuestos (requerido)
        self._agregar_total_impuestos(info_nc)
        
        # 17. Motivo (requerido)
        ET.SubElement(info_nc, 'motivo').text = self._limpiar_texto(self.nc.motivo)
    
    def _agregar_total_impuestos(self, parent):
        """Agrega el bloque totalConImpuestos"""
        total_impuestos = ET.SubElement(parent, 'totalConImpuestos')
        
        for ti in self.nc.totales_impuestos.all():
            total_impuesto = ET.SubElement(total_impuestos, 'totalImpuesto')
            
            ET.SubElement(total_impuesto, 'codigo').text = ti.codigo
            ET.SubElement(total_impuesto, 'codigoPorcentaje').text = ti.codigo_porcentaje
            ET.SubElement(total_impuesto, 'baseImponible').text = self._formatear_decimal(ti.base_imponible)
            ET.SubElement(total_impuesto, 'valor').text = self._formatear_decimal(ti.valor)
    
    def _agregar_detalles(self, root):
        """Agrega el bloque detalles"""
        detalles = ET.SubElement(root, 'detalles')
        
        for detalle in self.nc.detalles.all():
            det = ET.SubElement(detalles, 'detalle')
            
            # Código principal
            ET.SubElement(det, 'codigoInterno').text = detalle.codigo_principal
            
            # Código auxiliar (opcional)
            if detalle.codigo_auxiliar:
                ET.SubElement(det, 'codigoAdicional').text = detalle.codigo_auxiliar
            
            # Descripción
            ET.SubElement(det, 'descripcion').text = self._limpiar_texto(detalle.descripcion)
            
            # Cantidad
            ET.SubElement(det, 'cantidad').text = self._formatear_decimal(detalle.cantidad, 6)
            
            # Precio unitario
            ET.SubElement(det, 'precioUnitario').text = self._formatear_decimal(
                detalle.precio_unitario, 6
            )
            
            # Descuento
            ET.SubElement(det, 'descuento').text = self._formatear_decimal(detalle.descuento)
            
            # Precio total sin impuesto
            ET.SubElement(det, 'precioTotalSinImpuesto').text = self._formatear_decimal(
                detalle.precio_total_sin_impuesto
            )
            
            # Impuestos del detalle
            self._agregar_impuestos_detalle(det, detalle)
    
    def _agregar_impuestos_detalle(self, parent, detalle):
        """Agrega los impuestos de un detalle"""
        impuestos = ET.SubElement(parent, 'impuestos')
        impuesto = ET.SubElement(impuestos, 'impuesto')
        
        ET.SubElement(impuesto, 'codigo').text = '2'  # IVA
        ET.SubElement(impuesto, 'codigoPorcentaje').text = detalle.codigo_iva
        ET.SubElement(impuesto, 'tarifa').text = self._formatear_decimal(detalle.tarifa_iva)
        ET.SubElement(impuesto, 'baseImponible').text = self._formatear_decimal(
            detalle.precio_total_sin_impuesto
        )
        ET.SubElement(impuesto, 'valor').text = self._formatear_decimal(detalle.valor_iva)
    
    def _agregar_info_adicional(self, root):
        """Agrega el bloque infoAdicional (opcional)"""
        info_adicional = ET.SubElement(root, 'infoAdicional')
        
        # Email del cliente
        factura = self.nc.factura_modificada
        if factura.correo:
            campo = ET.SubElement(info_adicional, 'campoAdicional')
            campo.set('nombre', 'Email')
            campo.text = factura.correo
        
        # Teléfono del cliente
        if factura.telefono:
            campo = ET.SubElement(info_adicional, 'campoAdicional')
            campo.set('nombre', 'Teléfono')
            campo.text = factura.telefono
        
        # Dirección del cliente
        if factura.direccion:
            campo = ET.SubElement(info_adicional, 'campoAdicional')
            campo.set('nombre', 'Dirección')
            campo.text = self._limpiar_texto(factura.direccion)
    
    def _limpiar_texto(self, texto):
        """Limpia caracteres especiales del texto para XML"""
        if not texto:
            return ''
        
        texto = str(texto)
        
        # Eliminar saltos de línea (el XSD no permite \n en la mayoría de campos)
        texto = texto.replace('\n', ' ').replace('\r', ' ')
        
        # Eliminar caracteres de control (excepto espacios)
        texto = ''.join(char for char in texto if ord(char) >= 32)
        
        # Limitar longitud máxima según XSD (300 caracteres para la mayoría)
        if len(texto) > 300:
            texto = texto[:300]
        
        return texto.strip()
    
    def _formatear_decimal(self, valor, decimales=2):
        """Formatea un valor decimal para el XML"""
        if valor is None:
            valor = Decimal('0.00')
        
        if not isinstance(valor, Decimal):
            valor = Decimal(str(valor))
        
        formato = f'0.{"0" * decimales}'
        return str(valor.quantize(Decimal(formato), rounding=ROUND_HALF_UP))
    
    def generar_clave_acceso(self):
        """
        Genera la clave de acceso de 49 dígitos según especificación SRI
        """
        from random import randint
        
        # Fecha de emisión (ddmmaaaa)
        fecha = self.nc.fecha_emision.strftime('%d%m%Y')
        
        # Tipo de comprobante (04 = NC)
        tipo_comprobante = '04'
        
        # RUC del emisor
        ruc = self.empresa.ruc
        
        # Tipo de ambiente
        ambiente = '1' if self.opciones and self.opciones.tipo_ambiente == '1' else '2'
        
        # Serie (establecimiento + punto emisión)
        serie = self.nc.establecimiento + self.nc.punto_emision
        
        # Número de comprobante (secuencial)
        numero = self.nc.secuencial
        
        # Código numérico (8 dígitos aleatorios)
        codigo_numerico = str(randint(10000000, 99999999))
        
        # Tipo de emisión
        tipo_emision = '1'
        
        # Concatenar primeros 48 dígitos
        clave_sin_verificador = (
            fecha +              # 8 dígitos
            tipo_comprobante +   # 2 dígitos
            ruc +                # 13 dígitos
            ambiente +           # 1 dígito
            serie +              # 6 dígitos
            numero +             # 9 dígitos
            codigo_numerico +    # 8 dígitos
            tipo_emision         # 1 dígito
        )  # Total: 48 dígitos
        
        # Calcular dígito verificador (módulo 11)
        digito_verificador = self._calcular_digito_verificador(clave_sin_verificador)
        
        # Clave completa de 49 dígitos
        clave_acceso = clave_sin_verificador + str(digito_verificador)
        
        return clave_acceso
    
    def _calcular_digito_verificador(self, clave):
        """Calcula el dígito verificador módulo 11"""
        # Pesos para el cálculo
        pesos = [2, 3, 4, 5, 6, 7] * 8
        
        # Invertir la clave y multiplicar por pesos
        suma = 0
        for i, digito in enumerate(reversed(clave)):
            suma += int(digito) * pesos[i]
        
        # Calcular módulo 11
        residuo = suma % 11
        verificador = 11 - residuo
        
        # Ajustes especiales
        if verificador == 11:
            verificador = 0
        elif verificador == 10:
            verificador = 1
        
        return verificador
