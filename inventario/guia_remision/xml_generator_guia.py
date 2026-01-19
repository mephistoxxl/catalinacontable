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
    
    # IMPORTANTE: El XSD oficial de Guía (V1.1.0) es "no-namespace".
    # Por lo tanto, el XML NO debe declarar un namespace por defecto en <guiaRemision>.
    
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
                "guiaRemision",
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
            
            # Información adicional (opcional pero recomendado)
            info_adicional = self._generar_info_adicional()
            if info_adicional is not None:
                root.append(info_adicional)
            
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

    def validar_xml_contra_xsd(self, xml_content: str, xsd_path: str) -> dict:
        """Valida el XML de guía contra el XSD oficial.

        Returns:
            dict: { 'valido': bool, 'mensaje': str, 'errores': str (opcional) }
        """
        import os
        from lxml import etree

        if not os.path.exists(xsd_path):
            raise FileNotFoundError(f"Archivo XSD no encontrado: {xsd_path}")

        xsd_dir = os.path.dirname(xsd_path)
        # El XSD de guía está en inventario/guia_remision pero el xmldsig está en inventario/sri.
        # Resolver ambos escenarios.
        xmldsig_candidates = [
            os.path.join(xsd_dir, 'xmldsig-core-schema.xsd'),
        ]

        try:
            from django.conf import settings
            xmldsig_candidates.append(
                os.path.join(settings.BASE_DIR, 'inventario', 'sri', 'xmldsig-core-schema.xsd')
            )
        except Exception:
            pass

        xmldsig_path = next((p for p in xmldsig_candidates if os.path.exists(p)), None)

        with open(xsd_path, 'rb') as xsd_file:
            class SchemaResolver(etree.Resolver):
                def resolve(self, url, id, context):
                    if 'xmldsig' in url or 'xmldsig-core-schema' in url:
                        if xmldsig_path and os.path.exists(xmldsig_path):
                            return self.resolve_filename(xmldsig_path, context)
                    return None

            parser = etree.XMLParser()
            parser.resolvers.add(SchemaResolver())

            try:
                schema_doc = etree.parse(xsd_file, parser)
                schema = etree.XMLSchema(schema_doc)
            except etree.XMLSchemaParseError:
                xsd_file.seek(0)
                schema_root = etree.XML(xsd_file.read())
                schema = etree.XMLSchema(schema_root)

        try:
            xml_doc = etree.fromstring(xml_content.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            return {
                'valido': False,
                'mensaje': 'Error de sintaxis XML',
                'errores': f"Error de sintaxis en línea {e.lineno}: {e.msg}",
            }

        if schema.validate(xml_doc):
            return {
                'valido': True,
                'mensaje': 'XML válido según el esquema XSD del SRI',
            }

        errores = []
        for error in schema.error_log:
            errores.append(f"Línea {error.line}: {error.message}")

        return {
            'valido': False,
            'mensaje': 'XML inválido',
            'errores': "El XML no cumple con el XSD del SRI:\n" + "\n".join(errores),
        }
    
    def _generar_info_tributaria(self):
        """Genera la sección de información tributaria"""
        info_trib = etree.Element("infoTributaria")
        
        # Ambiente (1=Pruebas, 2=Producción)
        ambiente = etree.SubElement(info_trib, "ambiente")
        ambiente.text = str(self.opciones.tipo_ambiente if self.opciones else '1')
        
        # Tipo de emisión (1=Normal)
        tipo_emision = etree.SubElement(info_trib, "tipoEmision")
        tipo_emision.text = "1"
        
        # Razón social
        razon_social = etree.SubElement(info_trib, "razonSocial")
        razon_social.text = self.opciones.razon_social[:300] if self.opciones else "EMPRESA SIN CONFIGURAR"
        
        # Nombre comercial (opcional)
        if self.opciones and self.opciones.nombre_comercial:
            nombre_comercial_elem = etree.SubElement(info_trib, "nombreComercial")
            nombre_comercial_elem.text = str(self.opciones.nombre_comercial)[:300]
        
        # RUC
        ruc = etree.SubElement(info_trib, "ruc")
        ruc_value = self.opciones.ruc if self.opciones else '9999999999001'
        ruc.text = str(ruc_value)
        
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
        dir_matriz.text = self.opciones.direccion_establecimiento[:300] if self.opciones else "DIRECCION SIN CONFIGURAR"
        
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
            obligado_contabilidad.text = self.opciones.obligado if self.opciones.obligado else "NO"
        
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
        """Genera la sección de destinatarios desde la base de datos"""
        destinatarios_elem = etree.Element("destinatarios")
        
        # Obtener destinatarios reales de la base de datos
        destinatarios_db = self.guia.destinatarios.all()
        
        if not destinatarios_db.exists():
            # Si no hay destinatarios, usar datos básicos de la guía
            logger.warning(f"Guía {self.guia.id} no tiene destinatarios, usando datos básicos")
            destinatario = etree.SubElement(destinatarios_elem, "destinatario")
            
            identificacion = etree.SubElement(destinatario, "identificacionDestinatario")
            identificacion.text = "9999999999999"
            
            razon_social = etree.SubElement(destinatario, "razonSocialDestinatario")
            razon_social.text = "CONSUMIDOR FINAL"
            
            dir_dest = etree.SubElement(destinatario, "dirDestinatario")
            dir_dest.text = self.guia.direccion_destino[:300]
            
            motivo = etree.SubElement(destinatario, "motivoTraslado")
            motivo.text = "01"  # Venta por defecto
            
            # Detalles vacíos
            detalles = etree.SubElement(destinatario, "detalles")
            detalle = etree.SubElement(detalles, "detalle")
            
            codigo_interno = etree.SubElement(detalle, "codigoInterno")
            codigo_interno.text = "PROD001"
            
            descripcion = etree.SubElement(detalle, "descripcion")
            descripcion.text = "PRODUCTO TRANSPORTADO"
            
            cantidad = etree.SubElement(detalle, "cantidad")
            cantidad.text = "1.000000"
        else:
            # Generar XML para cada destinatario real
            for dest in destinatarios_db:
                destinatario = etree.SubElement(destinatarios_elem, "destinatario")
                
                # Identificación del destinatario
                identificacion = etree.SubElement(destinatario, "identificacionDestinatario")
                identificacion.text = dest.identificacion_destinatario[:20]
                
                # Razón social del destinatario
                razon_social = etree.SubElement(destinatario, "razonSocialDestinatario")
                razon_social.text = dest.razon_social_destinatario[:300]
                
                # Dirección del destinatario
                dir_dest = etree.SubElement(destinatario, "dirDestinatario")
                dir_dest.text = dest.dir_destinatario[:300]
                
                # Motivo traslado
                motivo = etree.SubElement(destinatario, "motivoTraslado")
                motivo.text = dest.motivo_traslado[:300]
                
                # Documento aduanero (opcional)
                if dest.doc_aduanero_unico:
                    doc_aduanero = etree.SubElement(destinatario, "docAduaneroUnico")
                    doc_aduanero.text = dest.doc_aduanero_unico[:20]
                
                # Código establecimiento destino (opcional)
                if dest.cod_estab_destino:
                    cod_estab_dest = etree.SubElement(destinatario, "codEstabDestino")
                    cod_estab_dest.text = dest.cod_estab_destino[:3]
                
                # Ruta (opcional)
                if dest.ruta:
                    ruta = etree.SubElement(destinatario, "ruta")
                    ruta.text = dest.ruta[:300]
                
                # ✅ Documento sustento (factura) - NUEVO según XSD SRI
                if dest.cod_doc_sustento and dest.num_doc_sustento:
                    cod_doc_sust = etree.SubElement(destinatario, "codDocSustento")
                    cod_doc_sust.text = dest.cod_doc_sustento[:2]
                    
                    num_doc_sust = etree.SubElement(destinatario, "numDocSustento")
                    num_doc_sust.text = dest.num_doc_sustento[:17]
                    
                    if dest.num_aut_doc_sustento:
                        num_aut_doc_sust = etree.SubElement(destinatario, "numAutDocSustento")
                        num_aut_doc_sust.text = dest.num_aut_doc_sustento[:49]
                    
                    if dest.fecha_emision_doc_sustento:
                        fecha_emision_doc_sust = etree.SubElement(destinatario, "fechaEmisionDocSustento")
                        fecha_emision_doc_sust.text = dest.fecha_emision_doc_sustento.strftime("%d/%m/%Y")
                
                # Detalles (productos/servicios transportados)
                detalles = etree.SubElement(destinatario, "detalles")
                
                # Obtener detalles del destinatario
                detalles_db = dest.detalles.all()
                
                if detalles_db.exists():
                    for det in detalles_db:
                        detalle = etree.SubElement(detalles, "detalle")
                        
                        # Código interno
                        codigo_interno = etree.SubElement(detalle, "codigoInterno")
                        codigo_interno.text = det.codigo_interno[:25]
                        
                        # Código adicional (opcional)
                        if det.codigo_adicional:
                            codigo_adicional = etree.SubElement(detalle, "codigoAdicional")
                            codigo_adicional.text = det.codigo_adicional[:25]
                        
                        # Descripción
                        descripcion = etree.SubElement(detalle, "descripcion")
                        descripcion.text = det.descripcion[:300]
                        
                        # Cantidad
                        cantidad = etree.SubElement(detalle, "cantidad")
                        # Formatear a 6 decimales
                        cantidad.text = f"{det.cantidad:.6f}"
                else:
                    # Si no hay detalles, agregar uno genérico
                    detalle = etree.SubElement(detalles, "detalle")
                    
                    codigo_interno = etree.SubElement(detalle, "codigoInterno")
                    codigo_interno.text = "PROD001"
                    
                    descripcion = etree.SubElement(detalle, "descripcion")
                    descripcion.text = "PRODUCTO TRANSPORTADO"
                    
                    cantidad = etree.SubElement(detalle, "cantidad")
                    cantidad.text = "1.000000"
        
        return destinatarios_elem
    
    def generar_clave_acceso(self):
        """
        Genera la clave de acceso de 49 dígitos según estándar SRI
        Formato: ddmmaaaa + codDoc + ruc + ambiente + serie + secuencial + códigoNumérico + tipoEmisión + dígitoVerificador
        
        Returns:
            str: Clave de acceso de 49 dígitos
        """
        from random import randint
        from datetime import datetime
        
        # 1. Fecha (8 dígitos) - ddmmaaaa
        fecha_obj = self.guia.fecha_inicio_traslado
        if isinstance(fecha_obj, str):
            # Convertir string a date
            fecha_obj = datetime.strptime(fecha_obj, '%Y-%m-%d').date()
        fecha = fecha_obj.strftime('%d%m%Y')
        
        # 2. Tipo de comprobante (2 dígitos) - 06 = Guía de Remisión
        tipo_comprobante = "06"
        
        # 3. RUC (13 dígitos)
        ruc = (self.opciones.identificacion if self.opciones else self.empresa.ruc).zfill(13)
        
        # 4. Ambiente (1 dígito) - 1=Pruebas, 2=Producción
        ambiente = str(self.opciones.tipo_ambiente if self.opciones else '1')
        
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
    
    def _generar_info_adicional(self):
        """
        Genera la sección de información adicional (opcional)
        Máximo 15 campos adicionales según XSD V1.1.0
        
        Returns:
            Element: Elemento infoAdicional o None si no hay información
        """
        campos_adicionales = []
        
        # Agregar correo si existe
        if self.guia.correo_envio:
            campos_adicionales.append({
                'nombre': 'Correo Electrónico',
                'valor': self.guia.correo_envio[:300]
            })
        
        # Agregar información adicional si existe
        if self.guia.informacion_adicional:
            campos_adicionales.append({
                'nombre': 'Información Adicional',
                'valor': self.guia.informacion_adicional[:300]
            })
        
        # Agregar ruta si existe
        if self.guia.ruta:
            campos_adicionales.append({
                'nombre': 'Ruta',
                'valor': self.guia.ruta[:300]
            })
        
        # Si no hay campos adicionales, retornar None
        if not campos_adicionales:
            return None
        
        # Crear elemento infoAdicional
        info_adicional = etree.Element("infoAdicional")
        
        # Agregar campos (máximo 15 según XSD)
        for campo in campos_adicionales[:15]:
            campo_elem = etree.SubElement(info_adicional, "campoAdicional")
            campo_elem.set("nombre", campo['nombre'][:300])
            campo_elem.text = campo['valor'][:300]
        
        return info_adicional
