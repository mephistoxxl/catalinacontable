"""
Generador de PDF tipo RIDE para GUÍAS DE REMISIÓN.
Cumple con especificaciones SRI para documentos electrónicos.
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import os
import io
import logging

logger = logging.getLogger(__name__)


class GuiaRemisionRIDEGenerator:
    """
    Generador de RIDE (Representación Impresa del Documento Electrónico) 
    para Guías de Remisión según normativa SRI Ecuador
    """
    
    def __init__(self):
        self.doc = None
        self.story = []
        self.styles = {}
        self.setup_styles()
    
    def setup_styles(self):
        """Configurar estilos para el documento PDF"""
        base_styles = getSampleStyleSheet()
        
        # Estilos personalizados para SRI
        self.styles = {
            'CabeceraGuia': ParagraphStyle(
                'CabeceraGuia',
                parent=base_styles['Heading1'],
                fontSize=14,
                textColor=colors.black,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=6,
            ),
            'DatosEmpresa': ParagraphStyle(
                'DatosEmpresa',
                parent=base_styles['Normal'],
                fontSize=8,
                textColor=colors.black,
                alignment=TA_LEFT,
                fontName='Helvetica',
                spaceAfter=3,
            ),
            'Campo': ParagraphStyle(
                'Campo',
                parent=base_styles['Normal'],
                fontSize=8,
                textColor=colors.black,
                alignment=TA_LEFT,
                fontName='Helvetica',
                spaceBefore=2,
                spaceAfter=2,
            ),
            'CampoValor': ParagraphStyle(
                'CampoValor',
                parent=base_styles['Normal'],
                fontSize=8,
                textColor=colors.black,
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceBefore=2,
                spaceAfter=2,
            ),
            'TablaHeader': ParagraphStyle(
                'TablaHeader',
                parent=base_styles['Normal'],
                fontSize=7,
                textColor=colors.black,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
            ),
            'TablaData': ParagraphStyle(
                'TablaData',
                parent=base_styles['Normal'],
                fontSize=7,
                textColor=colors.black,
                alignment=TA_LEFT,
                fontName='Helvetica',
            ),
        }
    
    def generar_ride_guia_remision(self, guia):
        """
        Genera el RIDE completo de la guía de remisión
        """
        buffer = io.BytesIO()
        
        # Configurar documento
        self.doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1*cm,
            leftMargin=1*cm,
            topMargin=1*cm,
            bottomMargin=1*cm,
            title=f"Guía de Remisión {guia.numero_completo}"
        )
        
        self.story = []
        
        # Construir contenido del documento
        self._agregar_cabecera(guia)
        self._agregar_datos_generales(guia)
        self._agregar_datos_destinatario(guia)
        self._agregar_datos_transportista(guia)
        self._agregar_detalle_productos(guia)
        self._agregar_informacion_adicional(guia)
        self._agregar_autorizacion_sri(guia)
        
        # Generar PDF
        self.doc.build(self.story)
        buffer.seek(0)
        
        return buffer
    
    def _agregar_cabecera(self, guia):
        """Agregar cabecera del documento con logo y datos de la empresa"""
        
        # TODO: Implementar logo de la empresa
        # if os.path.exists(ruta_logo):
        #     logo = Image(ruta_logo, width=2*cm, height=1.5*cm)
        #     self.story.append(logo)
        
        # Título principal
        titulo = Paragraph("GUÍA DE REMISIÓN", self.styles['CabeceraGuia'])
        self.story.append(titulo)
        self.story.append(Spacer(1, 0.3*cm))
        
        # Información de la empresa (TODO: obtener de configuración)
        datos_empresa = [
            ["RAZÓN SOCIAL:", "EMPRESA EJEMPLO S.A."],
            ["RUC:", "1234567890001"],
            ["DIRECCIÓN MATRIZ:", "Av. Ejemplo 123 y Calle Demo"],
            ["CONTRIBUYENTE ESPECIAL:", "No"],
            ["OBLIGADO A LLEVAR CONTABILIDAD:", "Sí"],
        ]
        
        tabla_empresa = Table(datos_empresa, colWidths=[4*cm, 10*cm])
        tabla_empresa.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        self.story.append(tabla_empresa)
        self.story.append(Spacer(1, 0.5*cm))
    
    def _agregar_datos_generales(self, guia):
        """Agregar datos generales de la guía"""
        
        # Crear tabla con datos generales
        datos_generales = [
            ["AMBIENTE:", "PRUEBAS" if guia.clave_acceso else "PRODUCCIÓN", "EMISIÓN:", "NORMAL"],
            ["RAZÓN SOCIAL / NOMBRES Y APELLIDOS:", guia.destinatario_nombre, "", ""],
            ["IDENTIFICACIÓN:", guia.destinatario_identificacion, "", ""],
            ["FECHA EMISIÓN:", guia.fecha_emision.strftime('%d/%m/%Y'), "GUÍA DE REMISIÓN:", guia.numero_completo],
        ]
        
        tabla_generales = Table(datos_generales, colWidths=[3*cm, 6*cm, 2.5*cm, 3.5*cm])
        tabla_generales.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ]))
        
        self.story.append(tabla_generales)
        self.story.append(Spacer(1, 0.3*cm))
    
    def _agregar_datos_destinatario(self, guia):
        """Agregar información del destinatario y direcciones"""
        
        # Título sección
        titulo = Paragraph("DESTINATARIO", self.styles['CabeceraGuia'])
        self.story.append(titulo)
        
        # Datos del destinatario
        datos_destinatario = [
            ["IDENTIFICACIÓN:", guia.destinatario_identificacion],
            ["RAZÓN SOCIAL / NOMBRES:", guia.destinatario_nombre],
            ["DIRECCIÓN DE PARTIDA:", guia.direccion_partida],
            ["DIRECCIÓN DESTINO:", guia.direccion_destino],
            ["MOTIVO TRASLADO:", guia.get_motivo_traslado_display()],
            ["FECHA INICIO TRASLADO:", guia.fecha_inicio_traslado.strftime('%d/%m/%Y %H:%M')],
            ["FECHA FIN TRASLADO:", guia.fecha_fin_traslado.strftime('%d/%m/%Y %H:%M') if guia.fecha_fin_traslado else "No especificado"],
        ]
        
        tabla_destinatario = Table(datos_destinatario, colWidths=[4*cm, 11*cm])
        tabla_destinatario.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        self.story.append(tabla_destinatario)
        self.story.append(Spacer(1, 0.3*cm))
    
    def _agregar_datos_transportista(self, guia):
        """Agregar información del transportista"""
        
        # Título sección
        titulo = Paragraph("DATOS DEL TRANSPORTISTA", self.styles['CabeceraGuia'])
        self.story.append(titulo)
        
        # Datos del transportista
        datos_transportista = [
            ["RUC / IDENTIFICACIÓN:", guia.transportista_ruc],
            ["RAZÓN SOCIAL / NOMBRES:", guia.transportista_nombre],
            ["PLACA:", guia.placa],
        ]
        
        if guia.transportista_observaciones:
            datos_transportista.append(["OBSERVACIONES:", guia.transportista_observaciones])
        
        tabla_transportista = Table(datos_transportista, colWidths=[4*cm, 11*cm])
        tabla_transportista.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        self.story.append(tabla_transportista)
        self.story.append(Spacer(1, 0.3*cm))
    
    def _agregar_detalle_productos(self, guia):
        """Agregar tabla con el detalle de productos"""
        
        # Título sección
        titulo = Paragraph("COMPROBANTES QUE SUSTENTAN EL TRASLADO", self.styles['CabeceraGuia'])
        self.story.append(titulo)
        
        # Encabezados de la tabla
        headers = ["CÓDIGO", "DESCRIPCIÓN", "CANTIDAD"]
        
        # Preparar datos de la tabla
        data = [headers]
        
        for detalle in guia.detalles.all():
            row = [
                detalle.codigo_producto,
                detalle.descripcion_producto,
                f"{detalle.cantidad:,.2f}",
            ]
            data.append(row)
        
        # Si no hay productos, agregar fila vacía
        if len(data) == 1:
            data.append(["", "No hay productos registrados", ""])
        
        # Crear tabla
        tabla_productos = Table(data, colWidths=[3*cm, 9*cm, 3*cm])
        tabla_productos.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Descripción alineada a la izquierda
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Headers en negrita
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]))
        
        self.story.append(tabla_productos)
        self.story.append(Spacer(1, 0.3*cm))
    
    def _agregar_informacion_adicional(self, guia):
        """Agregar información adicional y observaciones"""
        
        if guia.observaciones:
            titulo = Paragraph("INFORMACIÓN ADICIONAL", self.styles['CabeceraGuia'])
            self.story.append(titulo)
            
            observaciones = Paragraph(guia.observaciones, self.styles['Campo'])
            self.story.append(observaciones)
            self.story.append(Spacer(1, 0.3*cm))
    
    def _agregar_autorizacion_sri(self, guia):
        """Agregar información de autorización del SRI"""
        
        # Título sección
        titulo = Paragraph("INFORMACIÓN DE AUTORIZACIÓN", self.styles['CabeceraGuia'])
        self.story.append(titulo)
        
        # Datos de autorización
        if guia.estado == 'autorizada' and guia.clave_acceso:
            datos_autorizacion = [
                ["AUTORIZACIÓN:", guia.numero_autorizacion or "PENDIENTE"],
                ["FECHA AUTORIZACIÓN:", guia.fecha_autorizacion.strftime('%d/%m/%Y %H:%M:%S') if guia.fecha_autorizacion else "PENDIENTE"],
                ["CLAVE DE ACCESO:", guia.clave_acceso],
            ]
        else:
            datos_autorizacion = [
                ["ESTADO:", "PENDIENTE DE AUTORIZACIÓN"],
                ["CLAVE DE ACCESO:", "PENDIENTE"],
            ]
        
        tabla_autorizacion = Table(datos_autorizacion, colWidths=[4*cm, 11*cm])
        tabla_autorizacion.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ]))
        
        self.story.append(tabla_autorizacion)
        
        # TODO: Agregar código de barras con la clave de acceso
        # if guia.clave_acceso:
        #     self._agregar_codigo_barras(guia.clave_acceso)
    
    def generar_ride_guia_remision_file(self, guia, ruta_archivo):
        """
        Genera el archivo PDF de la guía de remisión en la ruta especificada
        """
        try:
            buffer = self.generar_ride_guia_remision(guia)
            
            with open(ruta_archivo, 'wb') as archivo:
                archivo.write(buffer.getvalue())
            
            logger.info(f"PDF de guía de remisión generado: {ruta_archivo}")
            return True
            
        except Exception as e:
            logger.error(f"Error al generar archivo PDF de guía de remisión: {str(e)}")
            return False
