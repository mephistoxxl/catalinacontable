"""
Generador de RIDE (Representación Impresa del Documento Electrónico)
para Notas de Crédito
"""
import os
import io
import logging
from decimal import Decimal
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, 
    Spacer, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

from django.conf import settings

logger = logging.getLogger(__name__)


class RIDEGeneratorNotaCredito:
    """
    Genera el PDF RIDE para Notas de Crédito
    """
    
    def __init__(self, nota_credito, opciones):
        """
        Args:
            nota_credito: Instancia de NotaCredito
            opciones: Instancia de Opciones de la empresa
        """
        self.nc = nota_credito
        self.opciones = opciones
        self.empresa = nota_credito.empresa
        
        # Configurar estilos
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """Configura estilos personalizados"""
        self.styles.add(ParagraphStyle(
            name='TituloEmpresa',
            parent=self.styles['Heading1'],
            fontSize=12,
            alignment=TA_CENTER,
            spaceAfter=2*mm
        ))
        
        self.styles.add(ParagraphStyle(
            name='DatosEmpresa',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            spaceAfter=1*mm
        ))
        
        self.styles.add(ParagraphStyle(
            name='TituloDocumento',
            parent=self.styles['Heading2'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.darkblue,
            spaceAfter=2*mm
        ))
        
        self.styles.add(ParagraphStyle(
            name='LabelCampo',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey
        ))
        
        self.styles.add(ParagraphStyle(
            name='ValorCampo',
            parent=self.styles['Normal'],
            fontSize=9
        ))
        
        self.styles.add(ParagraphStyle(
            name='Moneda',
            parent=self.styles['Normal'],
            fontSize=9,
            alignment=TA_RIGHT
        ))
    
    def _formatear_dinero(self, valor):
        """Formatea un valor como dinero"""
        if valor is None:
            return "$0.00"
        return f"${valor:,.2f}"
    
    def _get_logo(self):
        """Obtiene el logo de la empresa si existe"""
        if self.opciones and self.opciones.logo:
            try:
                # No usar `.path` (S3/no-local storage). Pasar por archivo temporal.
                with self.opciones.logo.open('rb') as f:
                    logo_bytes = f.read()
                if not logo_bytes:
                    return None

                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(self.opciones.logo.name or '')[1] or '.img')
                try:
                    tmp.write(logo_bytes)
                    tmp.flush()
                finally:
                    tmp.close()

                return Image(tmp.name, width=40*mm, height=20*mm)
            except Exception as e:
                logger.warning(f"No se pudo cargar el logo: {e}")
        return None
    
    def _generar_codigo_barras(self):
        """Genera código de barras con la clave de acceso"""
        try:
            from reportlab.graphics.barcode import code128
            clave = self.nc.clave_acceso or ''
            if len(clave) >= 10:
                barcode = code128.Code128(clave, barHeight=12*mm, barWidth=0.35)
                return barcode
        except Exception as e:
            logger.warning(f"No se pudo generar código de barras: {e}")
        return None
    
    def _crear_encabezado(self):
        """Crea el encabezado del documento"""
        elementos = []
        
        # Logo y datos empresa
        logo = self._get_logo()
        
        # Nombre comercial o razón social
        nombre_empresa = self.opciones.nombre_comercial if self.opciones.nombre_comercial else self.empresa.razon_social
        
        datos_empresa = [
            [Paragraph(f"<b>{nombre_empresa or 'EMPRESA'}</b>", self.styles['TituloEmpresa'])],
            [Paragraph(f"RUC: {self.empresa.ruc or ''}", self.styles['DatosEmpresa'])],
            [Paragraph(f"{self.opciones.direccion_matriz or ''}", self.styles['DatosEmpresa'])],
        ]
        
        if self.opciones.telefono:
            datos_empresa.append([Paragraph(f"Tel: {self.opciones.telefono}", self.styles['DatosEmpresa'])])
        
        tabla_empresa = Table(datos_empresa, colWidths=[100*mm])
        
        # Datos del documento
        ambiente = "PRODUCCIÓN" if self.opciones.tipo_ambiente == '2' else "PRUEBAS"
        
        datos_documento = [
            [Paragraph("<b>NOTA DE CRÉDITO</b>", self.styles['TituloDocumento'])],
            [Paragraph(f"No. {self.nc.numero_completo}", self.styles['ValorCampo'])],
            [Paragraph(f"Ambiente: {ambiente}", self.styles['LabelCampo'])],
            [Paragraph(f"Emisión: {self.opciones.get_tipo_emision_display() if hasattr(self.opciones, 'get_tipo_emision_display') else 'NORMAL'}", self.styles['LabelCampo'])],
        ]
        
        if self.nc.numero_autorizacion:
            datos_documento.append([Paragraph(f"<b>AUTORIZACIÓN:</b>", self.styles['LabelCampo'])])
            datos_documento.append([Paragraph(f"{self.nc.numero_autorizacion}", self.styles['ValorCampo'])])
        
        if self.nc.fecha_autorizacion:
            fecha_aut = self.nc.fecha_autorizacion.strftime("%d/%m/%Y %H:%M:%S")
            datos_documento.append([Paragraph(f"Fecha Auth: {fecha_aut}", self.styles['LabelCampo'])])
        
        tabla_documento = Table(datos_documento, colWidths=[80*mm])
        
        # Combinar logo, empresa y documento
        if logo:
            tabla_encabezado = Table(
                [[logo, tabla_empresa, tabla_documento]],
                colWidths=[45*mm, 80*mm, 65*mm]
            )
        else:
            tabla_encabezado = Table(
                [[tabla_empresa, tabla_documento]],
                colWidths=[110*mm, 80*mm]
            )
        
        tabla_encabezado.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
        ]))
        
        elementos.append(tabla_encabezado)
        elementos.append(Spacer(1, 3*mm))
        
        # Clave de acceso con código de barras
        if self.nc.clave_acceso:
            elementos.append(Paragraph("<b>CLAVE DE ACCESO:</b>", self.styles['LabelCampo']))
            elementos.append(Paragraph(self.nc.clave_acceso, self.styles['ValorCampo']))
            
            barcode = self._generar_codigo_barras()
            if barcode:
                elementos.append(Spacer(1, 2*mm))
                elementos.append(barcode)
        
        elementos.append(Spacer(1, 5*mm))
        
        return elementos
    
    def _crear_datos_comprador(self):
        """Crea la sección de datos del comprador"""
        elementos = []
        
        factura = self.nc.factura_modificada
        cliente = factura.cliente if factura else None

        identificacion = (
            (getattr(cliente, 'identificacion', None) if cliente else None)
            or (getattr(cliente, 'ruc', None) if cliente else None)
            or (getattr(cliente, 'cedula', None) if cliente else None)
            or (getattr(factura, 'identificacion_cliente', None) if factura else None)
            or ''
        )
        tipo_display = ''
        try:
            tipo_display = cliente.get_tipo_identificacion_display() if cliente else ''
        except Exception:
            tipo_display = ''
        
        datos = [
            ['Razón Social:', cliente.razon_social if cliente else ''],
            ['Identificación:', f"{tipo_display}: {identificacion}"],
            ['Dirección:', cliente.direccion if cliente else ''],
        ]
        
        tabla = Table(datos, colWidths=[40*mm, 150*mm])
        tabla.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        elementos.append(Paragraph("<b>ADQUIRENTE</b>", self.styles['TituloDocumento']))
        elementos.append(tabla)
        elementos.append(Spacer(1, 5*mm))
        
        return elementos
    
    def _crear_datos_factura_modificada(self):
        """Crea la sección de referencia a la factura modificada"""
        elementos = []
        
        factura = self.nc.factura_modificada
        
        datos = [
            ['Comprobante que modifica:', 'FACTURA'],
            ['Número:', factura.numero_completo if factura else ''],
            ['Fecha Emisión:', factura.fecha.strftime("%d/%m/%Y") if factura and factura.fecha else ''],
            ['Motivo:', self.nc.get_motivo_display() if hasattr(self.nc, 'get_motivo_display') else self.nc.motivo or ''],
        ]
        
        tabla = Table(datos, colWidths=[50*mm, 140*mm])
        tabla.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.95, 0.95, 0.95)),
        ]))
        
        elementos.append(Paragraph("<b>DOCUMENTO QUE MODIFICA</b>", self.styles['TituloDocumento']))
        elementos.append(tabla)
        elementos.append(Spacer(1, 5*mm))
        
        return elementos
    
    def _crear_detalle(self):
        """Crea la tabla de detalle de la nota de crédito"""
        elementos = []
        
        # Encabezados
        encabezados = ['Cant.', 'Código', 'Descripción', 'P. Unit.', 'Desc.', 'Subtotal']
        
        # Datos
        datos = [encabezados]
        
        for detalle in self.nc.detalles.all():
            fila = [
                f"{detalle.cantidad:.2f}" if detalle.cantidad else "0.00",
                detalle.codigo_principal or '',
                Paragraph(detalle.descripcion or '', self.styles['Normal']),
                self._formatear_dinero(detalle.precio_unitario),
                self._formatear_dinero(detalle.descuento or 0),
                self._formatear_dinero(detalle.precio_total_sin_impuesto),
            ]
            datos.append(fila)
        
        # Anchos de columna
        col_widths = [15*mm, 25*mm, 80*mm, 25*mm, 20*mm, 25*mm]
        
        tabla = Table(datos, colWidths=col_widths)
        tabla.setStyle(TableStyle([
            # Encabezados
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.3, 0.5)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Datos
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Cantidad
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),  # Precios
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ]))
        
        elementos.append(Paragraph("<b>DETALLE</b>", self.styles['TituloDocumento']))
        elementos.append(tabla)
        elementos.append(Spacer(1, 5*mm))
        
        return elementos
    
    def _crear_totales(self):
        """Crea la sección de totales"""
        elementos = []
        
        # Calcular valores
        subtotal_sin_iva = self.nc.total_sin_impuestos or Decimal('0.00')
        subtotal_iva = self.nc.subtotal_iva or Decimal('0.00')
        subtotal_0 = self.nc.subtotal_cero or Decimal('0.00')
        iva = self.nc.valor_iva or Decimal('0.00')
        total = self.nc.valor_modificacion or Decimal('0.00')
        
        # Datos de totales
        totales_data = [
            ['SUBTOTAL SIN IMPUESTOS:', self._formatear_dinero(subtotal_sin_iva)],
            ['SUBTOTAL IVA 15%:', self._formatear_dinero(subtotal_iva)],
            ['SUBTOTAL 0%:', self._formatear_dinero(subtotal_0)],
            ['IVA 15%:', self._formatear_dinero(iva)],
            ['VALOR TOTAL:', self._formatear_dinero(total)],
        ]
        
        tabla = Table(totales_data, colWidths=[50*mm, 30*mm])
        tabla.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        # Alinear a la derecha
        contenedor = Table([[tabla]], colWidths=[190*mm])
        contenedor.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ]))
        
        elementos.append(contenedor)
        elementos.append(Spacer(1, 10*mm))
        
        return elementos
    
    def _crear_informacion_adicional(self):
        """Crea la sección de información adicional"""
        elementos = []
        
        # Información adicional si existe
        info_adicional = []
        
        if self.nc.observaciones:
            info_adicional.append(['Observaciones:', self.nc.observaciones])
        
        if hasattr(self.nc, 'usuario') and self.nc.usuario:
            info_adicional.append(['Emitido por:', self.nc.usuario.username])
        
        if info_adicional:
            tabla = Table(info_adicional, colWidths=[40*mm, 150*mm])
            tabla.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            elementos.append(Paragraph("<b>INFORMACIÓN ADICIONAL</b>", self.styles['TituloDocumento']))
            elementos.append(tabla)
        
        return elementos
    
    def generar_pdf(self):
        """
        Genera el PDF de la Nota de Crédito
        Returns:
            BytesIO: Buffer con el contenido del PDF
        """
        buffer = io.BytesIO()
        
        # Crear documento
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=10*mm,
            leftMargin=10*mm,
            topMargin=10*mm,
            bottomMargin=15*mm
        )
        
        # Construir contenido
        elementos = []
        
        # Encabezado
        elementos.extend(self._crear_encabezado())
        
        # Datos del comprador
        elementos.extend(self._crear_datos_comprador())
        
        # Referencia a factura modificada
        elementos.extend(self._crear_datos_factura_modificada())
        
        # Detalle
        elementos.extend(self._crear_detalle())
        
        # Totales
        elementos.extend(self._crear_totales())
        
        # Información adicional
        elementos.extend(self._crear_informacion_adicional())
        
        # Construir PDF
        doc.build(elementos)
        
        buffer.seek(0)
        return buffer
    
    def guardar_pdf(self, directorio=None):
        """
        Guarda el PDF en el sistema de archivos
        Args:
            directorio: Directorio donde guardar (opcional)
        Returns:
            str: Ruta del archivo guardado
        """
        if directorio is None:
            directorio = os.path.join(
                settings.MEDIA_ROOT,
                'notas_credito_pdf',
                str(self.empresa.id)
            )
        
        os.makedirs(directorio, exist_ok=True)
        
        # Nombre del archivo
        numero_limpio = self.nc.numero_completo.replace('-', '_')
        nombre_archivo = f"nc_{numero_limpio}.pdf"
        ruta_completa = os.path.join(directorio, nombre_archivo)
        
        # Generar y guardar
        buffer = self.generar_pdf()
        with open(ruta_completa, 'wb') as f:
            f.write(buffer.getvalue())
        
        logger.info(f"PDF guardado en: {ruta_completa}")
        return ruta_completa
