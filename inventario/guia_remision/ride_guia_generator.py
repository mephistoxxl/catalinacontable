import logging
from io import BytesIO

from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from inventario.sri.ride_generator import RIDEGenerator

logger = logging.getLogger(__name__)


class GuiaRemisionRIDEGenerator(RIDEGenerator):
    MOTIVO_TRASLADO_LABELS = {
        '01': 'Venta',
        '02': 'Transformación',
        '03': 'Consignación',
        '04': 'Devolución',
        '05': 'Otros',
    }

    TIPO_IDENTIFICACION_LABELS = {
        '04': 'RUC',
        '05': 'Cédula',
        '06': 'Pasaporte',
        '07': 'Consumidor Final',
        '08': 'Identificación del exterior',
    }

    def __init__(self, empresa=None, opciones=None):
        self.empresa = empresa
        self.opciones = opciones
        super().__init__()

    def generar_ride_guia_remision(self, guia):
        opciones = self._resolve_opciones(guia)
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=8 * mm,
            leftMargin=8 * mm,
            topMargin=8 * mm,
            bottomMargin=34 * mm,
            title=f"Guía de Remisión {guia.numero_completo}",
        )
        elementos = []

        elementos.append(self._build_header_section(guia, opciones))
        elementos.append(Spacer(1, 10 * mm))
        elementos.append(self._build_destinatario_table(guia))
        elementos.append(Spacer(1, 4 * mm))
        elementos.append(self._build_transportista_table(guia))
        elementos.append(Spacer(1, 4 * mm))
        elementos.append(self._build_detalles_table(guia))

        info_adicional = self._build_info_adicional_table(guia)
        if info_adicional is not None:
            elementos.append(Spacer(1, 4 * mm))
            elementos.append(info_adicional)

        doc.build(
            elementos,
            onFirstPage=self._draw_catalinasoft_footer,
            onLaterPages=self._draw_catalinasoft_footer,
        )
        buffer.seek(0)
        return buffer

    def generar_ride_guia_remision_file(self, guia, ruta_archivo):
        try:
            buffer = self.generar_ride_guia_remision(guia)
            with open(ruta_archivo, 'wb') as archivo:
                archivo.write(buffer.getvalue())
            logger.info('PDF de guía de remisión generado: %s', ruta_archivo)
            return True
        except Exception as exc:
            logger.error('Error al generar archivo PDF de guía de remisión: %s', exc)
            return False

    def _resolve_opciones(self, guia):
        if self.opciones is not None:
            return self.opciones
        try:
            from inventario.models import Opciones

            self.opciones = Opciones.objects.for_tenant(getattr(guia, 'empresa', None)).first()
        except Exception as exc:
            logger.warning('No se pudieron resolver opciones para guía %s: %s', getattr(guia, 'id', None), exc)
            self.opciones = None
        return self.opciones

    def _build_header_section(self, guia, opciones):
        ancho_superior = 195
        espacio_entre = 8
        ancho_columna = (ancho_superior - espacio_entre) / 2

        logo = self._build_logo(opciones)
        datos_empresa = self._build_company_block(opciones)
        columna_izq = Table(
            [[logo], [Spacer(1, 2 * mm)], [datos_empresa]],
            colWidths=[ancho_columna * mm],
            rowHeights=[40 * mm, 2 * mm, 35 * mm],
        )
        columna_izq.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        cuadro_derecho = self._build_sri_box(guia, opciones, ancho_columna)
        tabla_superior = Table(
            [[columna_izq, '', cuadro_derecho]],
            colWidths=[ancho_columna * mm, espacio_entre * mm, ancho_columna * mm],
            rowHeights=[77 * mm],
        )
        tabla_superior.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return tabla_superior

    def _build_logo(self, opciones):
        if not opciones or not getattr(opciones, 'imagen', None):
            return ''
        try:
            with opciones.imagen.open('rb') as logo_file:
                logo_data = BytesIO(logo_file.read())
            reader = ImageReader(logo_data)
            orig_width, orig_height = reader.getSize()
            max_width = 45 * mm
            max_height = 40 * mm
            ratio = min(max_width / orig_width, max_height / orig_height)
            logo_data.seek(0)
            return Image(logo_data, width=orig_width * ratio, height=orig_height * ratio)
        except Exception as exc:
            logger.warning('No se pudo cargar el logo para RIDE de guía: %s', exc)
            return ''

    def _build_company_block(self, opciones):
        razon_social = getattr(opciones, 'razon_social', '') if opciones else ''
        nombre_comercial = getattr(opciones, 'nombre_comercial', '') if opciones else ''
        dir_matriz = getattr(opciones, 'direccion_matriz', getattr(opciones, 'direccion_establecimiento', '')) if opciones else ''
        dir_sucursal = getattr(opciones, 'direccion_establecimiento', '') if opciones else ''
        contribuyente_especial = getattr(opciones, 'contribuyente_especial', '') if opciones else ''
        obligado = getattr(opciones, 'obligado', 'NO') if opciones else 'NO'
        agente_retencion = getattr(opciones, 'agente_retencion', '') if opciones else ''

        linea_razon_social = f'<b>{razon_social}</b><br/>' if razon_social else ''
        linea_nombre_comercial = ''
        if nombre_comercial and nombre_comercial != '[CONFIGURAR NOMBRE COMERCIAL]' and nombre_comercial != razon_social:
            linea_nombre_comercial = f'<b>{nombre_comercial}</b><br/>'

        datos_empresa = f"""
{linea_razon_social}{linea_nombre_comercial}<b>Dirección Matriz:</b> {dir_matriz}<br/>
<b>Dirección Sucursal:</b> {dir_sucursal}<br/>
{'<b>Contribuyente Especial Nro</b> ' + contribuyente_especial + '<br/>' if contribuyente_especial else ''}
<b>OBLIGADO A LLEVAR CONTABILIDAD:</b> {obligado}<br/>
{f'<b>Agente de Retención Resolución No.</b> {agente_retencion}' if agente_retencion else ''}
"""
        cuadro_empresa = Table(
            [[Paragraph(datos_empresa, self.styles['DatosEmpresa'])]],
            colWidths=[93.5 * mm],
        )
        cuadro_empresa.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return cuadro_empresa

    def _build_sri_box(self, guia, opciones, ancho_columna):
        identificacion = getattr(opciones, 'identificacion', '') or getattr(getattr(guia, 'empresa', None), 'ruc', '')
        ambiente = getattr(opciones, 'ambiente_descripcion', '') if opciones else ''
        if not ambiente:
            ambiente = 'Pruebas' if str(getattr(opciones, 'tipo_ambiente', '1') if opciones else '1') == '1' else 'Producción'

        fecha_autorizacion = self._format_datetime(getattr(guia, 'fecha_autorizacion', None), default='PENDIENTE DE AUTORIZACIÓN')
        datos_info = [
            ['R.U.C.:', identificacion or 'N/A'],
            ['No.:', guia.numero_completo],
            ['NÚMERO DE AUTORIZACIÓN:', guia.numero_autorizacion or 'PENDIENTE'],
            ['FECHA Y HORA DE AUTORIZACIÓN:', fecha_autorizacion],
            ['AMBIENTE:', ambiente.capitalize()],
            ['EMISIÓN:', 'Normal'],
        ]

        filas = []
        for etiqueta, valor in datos_info:
            filas.append([
                Paragraph(f'<b>{etiqueta}</b>', self.styles['EtiquetaLimpia']),
                Paragraph(str(valor), self.styles['ValorLimpio']),
            ])

        tabla_datos = Table(filas, colWidths=[35 * mm, 55 * mm])
        tabla_datos.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))

        try:
            barcode = code128.Code128(guia.clave_acceso or '', barHeight=8 * mm, barWidth=0.28 * mm, humanReadable=False)
        except Exception:
            barcode = Paragraph('Código de barras no disponible', self.styles['ClaveAcceso'])

        bloque_clave = Table([
            [Paragraph('<b>CLAVE DE ACCESO</b>', self.styles['EtiquetaLimpia'])],
            [barcode],
            [Paragraph(guia.clave_acceso or 'N/A', self.styles['ClaveAcceso'])],
        ], colWidths=[80 * mm])
        bloque_clave.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))

        cuadro = Table([
            [Paragraph('GUÍA DE REMISIÓN', self.styles['EncabezadoLimpio'])],
            [tabla_datos],
            [bloque_clave],
        ], colWidths=[ancho_columna * mm], rowHeights=[19 * mm, 35 * mm, 23 * mm])
        cuadro.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.10, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (-1, 1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 1), (0, 1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return cuadro

    def _build_destinatario_table(self, guia):
        destinatario = self._get_primary_destinatario(guia)
        nombre = self._get_destinatario_nombre(guia)
        identificacion = self._get_destinatario_identificacion(guia)
        direccion_destino = self._get_destinatario_direccion(guia)
        motivo = self._get_motivo_traslado(guia)
        ruta = getattr(destinatario, 'ruta', '') if destinatario else getattr(guia, 'ruta', '')

        data = [
            [
                Paragraph(f'<b>Razón Social / Nombres y Apellidos:</b> {nombre}', self.styles['Campo']),
                Paragraph(f'<b>Identificación:</b> {identificacion}', self.styles['Campo']),
            ],
            [
                Paragraph(f'<b>Fecha de Emisión:</b> {self._format_date(getattr(guia, "fecha_inicio_traslado", None))}', self.styles['Campo']),
                Paragraph(f'<b>Guía de Remisión:</b> {guia.numero_completo}', self.styles['Campo']),
            ],
            [
                Paragraph(f'<b>Dirección de Partida:</b> {getattr(guia, "direccion_partida", "") or "N/A"}', self.styles['Campo']),
                Paragraph(f'<b>Dirección Destino:</b> {direccion_destino}', self.styles['Campo']),
            ],
            [
                Paragraph(f'<b>Motivo de Traslado:</b> {motivo}', self.styles['Campo']),
                Paragraph(f'<b>Ruta:</b> {ruta or "N/A"}', self.styles['Campo']),
            ],
        ]
        tabla = Table(data, colWidths=[97.5 * mm, 97.5 * mm])
        tabla.setStyle(self._box_table_style())
        return tabla

    def _build_transportista_table(self, guia):
        fecha_fin = getattr(guia, 'fecha_fin_traslado', None) or getattr(guia, 'fecha_inicio_traslado', None)
        data = [
            [
                Paragraph(f'<b>Transportista:</b> {getattr(guia, "transportista_nombre", "") or "N/A"}', self.styles['Campo']),
                Paragraph(f'<b>RUC / Identificación:</b> {getattr(guia, "transportista_ruc", "") or "N/A"}', self.styles['Campo']),
            ],
            [
                Paragraph(f'<b>Placa:</b> {getattr(guia, "placa", "") or "N/A"}', self.styles['Campo']),
                Paragraph(f'<b>Tipo de Identificación:</b> {self._get_tipo_identificacion_transportista_label(guia)}', self.styles['Campo']),
            ],
            [
                Paragraph(f'<b>Fecha Inicio Traslado:</b> {self._format_date(getattr(guia, "fecha_inicio_traslado", None))}', self.styles['Campo']),
                Paragraph(f'<b>Fecha Fin Traslado:</b> {self._format_date(fecha_fin)}', self.styles['Campo']),
            ],
        ]
        tabla = Table(data, colWidths=[97.5 * mm, 97.5 * mm])
        tabla.setStyle(self._box_table_style())
        return tabla

    def _build_detalles_table(self, guia):
        data = [[
            Paragraph('<b>Código Principal</b>', self.styles['Campo']),
            Paragraph('<b>Descripción</b>', self.styles['Campo']),
            Paragraph('<b>Cantidad</b>', self.styles['Campo']),
        ]]

        detalles = self._collect_detalles(guia)
        if not detalles:
            data.append(['', Paragraph('No hay productos registrados', self.styles['Campo']), ''])
        else:
            for detalle in detalles:
                descripcion = getattr(detalle, 'descripcion', '') or getattr(detalle, 'descripcion_producto', '') or ''
                extras = []
                destinatario_nombre = getattr(detalle, '_ride_destinatario_nombre', '')
                if destinatario_nombre:
                    extras.append(f'Destinatario: {destinatario_nombre}')
                documento_sustento = getattr(detalle, '_ride_doc_sustento', '')
                if documento_sustento:
                    extras.append(f'Doc. sustento: {documento_sustento}')
                observaciones = (getattr(detalle, 'observaciones', '') or '').strip()
                if observaciones:
                    extras.append(f'Obs: {observaciones}')
                if extras:
                    descripcion = f'{descripcion}<br/><font size="7">{" | ".join(extras)}</font>'
                data.append([
                    Paragraph(str(getattr(detalle, 'codigo_interno', '') or getattr(detalle, 'codigo_producto', '') or ''), self.styles['Campo']),
                    Paragraph(descripcion, self.styles['Campo']),
                    Paragraph(self._format_quantity(getattr(detalle, 'cantidad', None)), self.styles['NumericoDecimals']),
                ])

        tabla = Table(data, colWidths=[32 * mm, 123 * mm, 40 * mm], repeatRows=1)
        tabla.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.10, colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.10, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        return tabla

    def _collect_detalles(self, guia):
        detalles = []

        try:
            for destinatario in guia.destinatarios.order_by('id').prefetch_related('detalles'):
                for detalle in destinatario.detalles.all():
                    detalle._ride_destinatario_nombre = getattr(destinatario, 'razon_social_destinatario', '') or ''
                    detalle._ride_doc_sustento = getattr(destinatario, 'num_doc_sustento', '') or ''
                    detalles.append(detalle)
        except Exception as exc:
            logger.warning('No se pudieron cargar detalles por destinatario para guía %s: %s', getattr(guia, 'id', None), exc)

        if detalles:
            return detalles

        try:
            return list(guia.detalles.all())
        except Exception:
            return []

    def _build_info_adicional_table(self, guia):
        destinatario = self._get_primary_destinatario(guia)
        info_adicional = []

        informacion = (getattr(guia, 'informacion_adicional', '') or '').strip()
        if informacion:
            info_adicional.append([Paragraph(f'<b>Información adicional:</b> {informacion}', self.styles['Campo'])])

        doc_sustento = getattr(destinatario, 'num_doc_sustento', '') if destinatario else ''
        if doc_sustento:
            info_adicional.append([Paragraph(f'<b>Documento sustento:</b> {doc_sustento}', self.styles['Campo'])])

        autorizacion = getattr(guia, 'numero_autorizacion', '') or 'PENDIENTE'
        info_adicional.append([Paragraph(f'<b>Número de autorización:</b> {autorizacion}', self.styles['Campo'])])

        if not info_adicional:
            return None

        tabla = Table(info_adicional, colWidths=[195 * mm])
        tabla.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.10, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return tabla

    def _box_table_style(self):
        return TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.10, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ])

    def _get_primary_destinatario(self, guia):
        try:
            return guia.destinatarios.order_by('id').first()
        except Exception:
            return None

    def _get_destinatario_nombre(self, guia):
        destinatario = self._get_primary_destinatario(guia)
        if destinatario and getattr(destinatario, 'razon_social_destinatario', ''):
            return destinatario.razon_social_destinatario
        factura = getattr(guia, 'factura', None)
        return getattr(factura, 'nombre_cliente', '') or 'Destinatario'

    def _get_destinatario_identificacion(self, guia):
        destinatario = self._get_primary_destinatario(guia)
        if destinatario and getattr(destinatario, 'identificacion_destinatario', ''):
            return destinatario.identificacion_destinatario
        factura = getattr(guia, 'factura', None)
        return getattr(factura, 'identificacion_cliente', '') or 'N/A'

    def _get_destinatario_direccion(self, guia):
        destinatario = self._get_primary_destinatario(guia)
        if destinatario and getattr(destinatario, 'dir_destinatario', ''):
            return destinatario.dir_destinatario
        return getattr(guia, 'direccion_destino', '') or 'N/A'

    def _get_motivo_traslado(self, guia):
        destinatario = self._get_primary_destinatario(guia)
        if destinatario and getattr(destinatario, 'motivo_traslado', ''):
            motivo = destinatario.motivo_traslado
            return self.MOTIVO_TRASLADO_LABELS.get(str(motivo).strip(), motivo)
        return 'Traslado de mercadería'

    def _get_tipo_identificacion_transportista_label(self, guia):
        tipo = str(getattr(guia, 'tipo_identificacion_transportista', '') or '').strip()
        return self.TIPO_IDENTIFICACION_LABELS.get(tipo, tipo or 'N/A')

    def _format_date(self, value, default='N/A'):
        if not value:
            return default
        try:
            return value.strftime('%d/%m/%Y')
        except Exception:
            return str(value)

    def _format_datetime(self, value, default='N/A'):
        if not value:
            return default
        try:
            return value.strftime('%d/%m/%Y %H:%M:%S')
        except Exception:
            return str(value)

    def _format_quantity(self, value):
        if value is None:
            return '0.00'
        try:
            return f'{float(value):.2f}'
        except Exception:
            return str(value)
