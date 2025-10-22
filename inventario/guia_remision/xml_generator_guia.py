"""
Generador de XML para Guías de Remisión - SRI Ecuador
Completamente independiente del generador de facturas
"""
import logging
from datetime import datetime
from lxml import etree
from decimal import Decimal

logger = logging.getLogger(__name__)


class XMLGeneratorGuiaRemision:
    """
    Genera el XML de Guías de Remisión según el esquema del SRI Ecuador
    """
    
    # Namespaces para Guía de Remisión
    NAMESPACE = "http://www.sri.gob.ec/DocElectronicos/guiaRemision/V1.1.0"
    
    def __init__(self, guia, empresa, opciones):
        """
        Inicializa el generador con los datos de la guía
        
        Args:
            guia: Instancia del modelo GuiaRemision
            empresa: Instancia del modelo Empresa
            opciones: Instancia del modelo Opciones
        """
        self.guia = guia
        self.empresa = empresa
        self.opciones = opciones
    
    def generar_xml(self):
        """
        Genera el XML completo de la guía de remisión
        
        Returns:
            str: XML en formato string
        """
        try:
            # Crear elemento raíz
            root = etree.Element(
                "{%s}guiaRemision" % self.NAMESPACE,
                nsmap={None: self.NAMESPACE},
                id="comprobante",
                version="1.1.0"
            )
            
            # Información tributaria
            info_tributaria = self._generar_info_tributaria()
            root.append(info_tributaria)
            
            # Información de la guía de remisión
            info_guia = self._generar_info_guia_remision()
            root.append(info_guia)
            
            # Destinatarios
            destinatarios_elem = self._generar_destinatarios()
            root.append(destinatarios_elem)
            
            # Convertir a string con formato
            xml_string = etree.tostring(
                root,
                pretty_print=True,
                xml_declaration=True,
                encoding='UTF-8'
            ).decode('utf-8')
            
            logger.info(f"XML generado exitosamente para guía {self.guia.numero_completo}")
            return xml_string
            
        except Exception as e:
            logger.error(f"Error generando XML de guía de remisión: {e}")
            raise
    
    def _generar_info_tributaria(self):
        """Genera la sección de información tributaria"""
        info_trib = etree.Element("infoTributaria")
        
        # Ambiente (1=Pruebas, 2=Producción)
        ambiente = etree.SubElement(info_trib, "ambiente")
        ambiente.text = str(self.opciones.ambiente_sri if self.opciones else 1)
        
        # Tipo de emisión (1=Normal)
        tipo_emision = etree.SubElement(info_trib, "tipoEmision")
        tipo_emision.text = "1"
        
        # Razón social
        razon_social = etree.SubElement(info_trib, "razonSocial")
        razon_social.text = self.empresa.razon_social[:300]
        
        # Nombre comercial
        if self.empresa.nombre_comercial:
            nombre_comercial = etree.SubElement(info_trib, "nombreComercial")
            nombre_comercial.text = self.empresa.nombre_comercial[:300]
        
        # RUC
        ruc = etree.SubElement(info_trib, "ruc")
        ruc.text = self.opciones.ruc if self.opciones else self.empresa.ruc
        
        # Clave de acceso
        clave_acceso = etree.SubElement(info_trib, "claveAcceso")
        clave_acceso.text = self.guia.clave_acceso
        
        # Código del documento (06 = Guía de Remisión)
        cod_doc = etree.SubElement(info_trib, "codDoc")
        cod_doc.text = "06"
        
        # Establecimiento
        estab = etree.SubElement(info_trib, "estab")
        estab.text = self.guia.establecimiento
        
        # Punto de emisión
        pto_emi = etree.SubElement(info_trib, "ptoEmi")
        pto_emi.text = self.guia.punto_emision
        
        # Secuencial
        secuencial = etree.SubElement(info_trib, "secuencial")
        secuencial.text = self.guia.secuencial.zfill(9)
        
        # Dirección matriz
        dir_matriz = etree.SubElement(info_trib, "dirMatriz")
        dir_matriz.text = self.empresa.direccion[:300]
        
        return info_trib
    
    def _generar_info_guia_remision(self):
        """Genera la sección de información de la guía de remisión"""
        info_guia = etree.Element("infoGuiaRemision")
        
        # Dirección del establecimiento (opcional pero recomendado)
        if self.guia.dir_establecimiento:
            dir_estab = etree.SubElement(info_guia, "dirEstablecimiento")
            dir_estab.text = self.guia.dir_establecimiento[:300]
        
        # Dirección de partida
        dir_partida = etree.SubElement(info_guia, "dirPartida")
        dir_partida.text = self.guia.direccion_partida[:300]
        
        # Razón social transportista
        razon_social_transp = etree.SubElement(info_guia, "razonSocialTransportista")
        razon_social_transp.text = self.guia.transportista_nombre[:300] if self.guia.transportista_nombre else "TRANSPORTISTA"
        
        # Tipo identificación transportista (CAMPO CRÍTICO - usa el nuevo campo del modelo)
        tipo_id_transp = etree.SubElement(info_guia, "tipoIdentificacionTransportista")
        tipo_id_transp.text = self.guia.tipo_identificacion_transportista
        
        # RUC/Cédula transportista
        ruc_transp = etree.SubElement(info_guia, "rucTransportista")
        ruc_transp.text = self.guia.transportista_ruc
        
        # RISE (opcional)
        if self.guia.rise:
            rise = etree.SubElement(info_guia, "rise")
            rise.text = self.guia.rise[:40]
        
        # Obligado a llevar contabilidad
        if self.guia.obligado_contabilidad:
            obligado_contabilidad = etree.SubElement(info_guia, "obligadoContabilidad")
            obligado_contabilidad.text = self.guia.obligado_contabilidad
        elif self.opciones:
            obligado_contabilidad = etree.SubElement(info_guia, "obligadoContabilidad")
            obligado_contabilidad.text = self.opciones.obligado_contabilidad if hasattr(self.opciones, 'obligado_contabilidad') else "NO"
        
        # Contribuyente especial (si aplica)
        if self.guia.contribuyente_especial:
            contrib_especial = etree.SubElement(info_guia, "contribuyenteEspecial")
            contrib_especial.text = self.guia.contribuyente_especial[:13]
        elif self.opciones and hasattr(self.opciones, 'contribuyente_especial') and self.opciones.contribuyente_especial:
            contrib_especial = etree.SubElement(info_guia, "contribuyenteEspecial")
            contrib_especial.text = self.opciones.contribuyente_especial[:13]
        
        # Fecha inicio transporte
        fecha_ini = etree.SubElement(info_guia, "fechaIniTransporte")
        fecha_ini.text = self.guia.fecha_inicio_traslado.strftime("%d/%m/%Y")
        
        # Fecha fin transporte
        fecha_fin = etree.SubElement(info_guia, "fechaFinTransporte")
        if self.guia.fecha_fin_traslado:
            fecha_fin.text = self.guia.fecha_fin_traslado.strftime("%d/%m/%Y")
        else:
            # Si no hay fecha fin, usar la misma que fecha inicio
            fecha_fin.text = self.guia.fecha_inicio_traslado.strftime("%d/%m/%Y")
        
        # Placa
        placa = etree.SubElement(info_guia, "placa")
        placa.text = self.guia.placa[:20]
        
        return info_guia
    
    def _generar_destinatarios(self):
        """Genera la sección de destinatarios"""
        destinatarios = etree.Element("destinatarios")
        
        # Aquí irán los destinatarios desde la tabla
        # Por ahora dejamos un destinatario básico
        destinatario = etree.SubElement(destinatarios, "destinatario")
        
        # Identificación del destinatario
        identificacion = etree.SubElement(destinatario, "identificacionDestinatario")
        identificacion.text = "9999999999999"  # Consumidor final por defecto
        
        # Razón social del destinatario
        razon_social = etree.SubElement(destinatario, "razonSocialDestinatario")
        razon_social.text = "CONSUMIDOR FINAL"
        
        # Dirección del destinatario
        dir_dest = etree.SubElement(destinatario, "dirDestinatario")
        dir_dest.text = self.guia.direccion_destino[:300]
        
        # Motivo traslado
        motivo = etree.SubElement(destinatario, "motivoTraslado")
        motivo.text = "VENTA"
        
        # Ruta (opcional)
        if self.guia.ruta:
            ruta = etree.SubElement(destinatario, "ruta")
            ruta.text = self.guia.ruta[:300]
        
        # Documento aduanero (opcional - para futuro)
        # doc_aduanero = etree.SubElement(destinatario, "docAduaneroUnico")
        
        # Código establecimiento destino (opcional)
        cod_estab_dest = etree.SubElement(destinatario, "codEstabDestino")
        cod_estab_dest.text = "001"
        
        # Detalles (productos/servicios transportados)
        detalles = etree.SubElement(destinatario, "detalles")
        
        # Detalle ejemplo (esto debe venir de la base de datos en el futuro)
        detalle = etree.SubElement(detalles, "detalle")
        
        codigo_interno = etree.SubElement(detalle, "codigoInterno")
        codigo_interno.text = "PROD001"
        
        descripcion = etree.SubElement(detalle, "descripcion")
        descripcion.text = "PRODUCTO TRANSPORTADO"
        
        cantidad = etree.SubElement(detalle, "cantidad")
        cantidad.text = "1.000000"
        
        return destinatarios
    
    def generar_clave_acceso(self):
        """
        Genera la clave de acceso de 49 dígitos según estándar SRI
        Formato: ddmmaaaa + codDoc + ruc + ambiente + serie + secuencial + códigoNumérico + tipoEmisión + dígitoVerificador
        
        Returns:
            str: Clave de acceso de 49 dígitos
        """
        from random import randint
        
        # 1. Fecha (8 dígitos) - ddmmaaaa
        fecha = self.guia.fecha_inicio_traslado.strftime('%d%m%Y')
        
        # 2. Tipo de comprobante (2 dígitos) - 06 = Guía de Remisión
        tipo_comprobante = "06"
        
        # 3. RUC (13 dígitos)
        ruc = (self.opciones.ruc if self.opciones else self.empresa.ruc).zfill(13)
        
        # 4. Ambiente (1 dígito) - 1=Pruebas, 2=Producción
        ambiente = str(self.opciones.ambiente_sri if self.opciones else 1)
        
        # 5. Serie (6 dígitos) - establecimiento + punto emisión
        serie = f"{self.guia.establecimiento}{self.guia.punto_emision}"
        
        # 6. Secuencial (9 dígitos)
        secuencial = self.guia.secuencial.zfill(9)
        
        # 7. Código numérico (8 dígitos) - Aleatorio
        codigo_numerico = str(randint(10000000, 99999999))
        
        # 8. Tipo de emisión (1 dígito) - 1=Normal
        tipo_emision = "1"
        
        # Concatenar primeros 48 dígitos
        clave_sin_verificador = (
            fecha + tipo_comprobante + ruc + ambiente + 
            serie + secuencial + codigo_numerico + tipo_emision
        )
        
        # 9. Dígito verificador (módulo 11)
        digito_verificador = self._calcular_digito_verificador(clave_sin_verificador)
        
        # Clave completa
        clave_acceso = clave_sin_verificador + str(digito_verificador)
        
        logger.info(f"Clave de acceso generada: {clave_acceso}")
        return clave_acceso
    
    def _calcular_digito_verificador(self, clave):
        """
        Calcula el dígito verificador usando módulo 11
        
        Args:
            clave (str): Primeros 48 dígitos de la clave
            
        Returns:
            int: Dígito verificador
        """
        # Multiplicadores del módulo 11 (repetidos cíclicamente)
        multiplicadores = [2, 3, 4, 5, 6, 7]
        suma = 0
        
        # Recorrer de derecha a izquierda
        for i, digito in enumerate(reversed(clave)):
            multiplicador = multiplicadores[i % 6]
            suma += int(digito) * multiplicador
        
        # Calcular residuo
        residuo = suma % 11
        
        # Calcular dígito verificador
        if residuo == 0:
            return 0
        elif residuo == 1:
            return 0  # Por convención del SRI
        else:
            return 11 - residuo
