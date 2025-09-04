"""
Generador de PDF tipo RIDE para PROFORMAS (separado del RIDE de facturas).
No usa Clave de Acceso ni datos SRI; diseño limpio, monocromático, A4.
"""

import os
import base64
import qrcode
from io import BytesIO
from datetime import datetime
from pathlib import Path
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from xml.etree import ElementTree as ET
import logging

logger = logging.getLogger(__name__)

class ProformaRIDEGenerator:
    """Generador de PDF para PROFORMAS usando ReportLab (independiente del RIDE de facturas)."""
    
    def __init__(self):
        self.setup_styles()
        # Sin colores - diseño limpio
        self.color_fondo = colors.white
        self.color_borde = colors.black
        
    def setup_styles(self):
        """Configurar estilos para el PDF exactos al SRI"""
        self.styles = getSampleStyleSheet()
        
        # Estilo para texto en cabeceras - SIN FONDO AZUL
        self.styles.add(ParagraphStyle(
            name='CabeceraBlanca',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold',
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceAfter=0
        ))
        
        # Estilo para datos de empresa (más compacto y alineado a la derecha)
        self.styles.add(ParagraphStyle(
            name='DatosEmpresa',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            alignment=TA_RIGHT,
            spaceAfter=1,
            leading=10
        ))
        
        # Estilo para campos normales (más compacto)
        self.styles.add(ParagraphStyle(
            name='Campo',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            alignment=TA_LEFT,
            spaceAfter=0,
            leading=9
        ))
        
        # Estilo para encabezado - LIMPIO SIN COLORES
        self.styles.add(ParagraphStyle(
            name='EncabezadoLimpio',
            parent=self.styles['Normal'],
            fontSize=13,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=2,
            leading=15
        ))
        
        # Estilo para etiquetas - LIMPIO
        self.styles.add(ParagraphStyle(
            name='EtiquetaLimpia',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=0,
            leading=9
        ))
        
        # Estilo para valores - LIMPIO  
        self.styles.add(ParagraphStyle(
            name='ValorLimpio',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            alignment=TA_LEFT,
            spaceAfter=0,
            leading=9
        ))
        
        # Estilo para valores numéricos
        self.styles.add(ParagraphStyle(
            name='NumericoDecimals',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            alignment=TA_RIGHT,
            spaceAfter=1
        ))
        
        # Estilo para clave de acceso - COMPACTO Y LIMPIO
        self.styles.add(ParagraphStyle(
            name='ClaveAcceso',
            parent=self.styles['Normal'],
            fontSize=7,
            fontName='Courier',
            alignment=TA_CENTER,
            spaceAfter=1,
            leading=8
        ))

    def _fmt_num(self, val, decimals=2):
        """Formatea números como 1.234,56 sin símbolo de moneda.
        Acepta float/Decimal/str.
        """
        try:
            x = float(val or 0)
        except Exception:
            x = 0.0
        s = f"{x:,.{decimals}f}"  # 1,234.56
        # Convertir a formato ES: 1.234,56
        s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
        return s

    def generar_codigo_barras(self, clave_acceso):
        """Generar código de barras horizontal con la clave de acceso"""
        try:
            from reportlab.graphics.barcode import code128
            from reportlab.graphics import renderPDF
            from reportlab.graphics.shapes import Drawing
            
            # Crear código de barras horizontal MÁS COMPACTO
            barcode = code128.Code128(clave_acceso, barHeight=6*mm, barWidth=0.3*mm)
            drawing = Drawing(90*mm, 8*mm)
            drawing.add(barcode)
            
            # Convertir a imagen
            img_buffer = BytesIO()
            renderPDF.drawToFile(drawing, img_buffer, fmt='PNG')
            img_buffer.seek(0)
            
            return Image(img_buffer, width=90*mm, height=8*mm)
        except Exception as e:
            logger.error(f"Error generando código de barras: {e}")
            return self._crear_codigo_barras_simple(clave_acceso)
    
    def _crear_codigo_barras_simple(self, clave_acceso):
        """Crear representación simple de código de barras"""
        try:
            from reportlab.lib.utils import ImageReader
            from PIL import Image as PILImage, ImageDraw
            
            # Crear imagen con líneas verticales simulando código de barras
            width, height = 300, 20
            img = PILImage.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)
            
            # Dibujar líneas verticales alternadas
            x = 10
            for i, char in enumerate(clave_acceso[:40]):
                if i % 2 == 0:
                    draw.rectangle([x, 2, x+1, height-2], fill='black')
                x += 2
            
            img_buffer = BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            return Image(img_buffer, width=90*mm, height=8*mm)
        except Exception as e:
            logger.error(f"Error creando código de barras simple: {e}")
            return None

    def generar_ride_proforma(self, proforma, detalles, opciones, output_path):
        """Generar PDF de PROFORMA (sin datos SRI)."""
        try:
            from reportlab.platypus import Spacer
            logger.info(f"Generando PROFORMA {getattr(proforma, 'numero', getattr(proforma, 'id', ''))}")
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=8*mm,
                leftMargin=8*mm,
                topMargin=8*mm,
                bottomMargin=8*mm
            )
            elementos = []

            # === FILA SUPERIOR: LOGO + DATOS EMPRESA  |  CUADRO AZUL REORGANIZADO ===
            # Logo
            logo_abspath = None
            if hasattr(opciones, 'imagen') and opciones.imagen:
                logo_abspath = opciones.imagen.path if hasattr(opciones.imagen, 'path') else str(opciones.imagen)
            if logo_abspath and os.path.exists(logo_abspath):
                try:
                    from reportlab.lib.utils import ImageReader
                    reader = ImageReader(logo_abspath)
                    orig_width, orig_height = reader.getSize()
                    max_width = 45 * mm
                    max_height = 40 * mm
                    ratio = min(max_width / orig_width, max_height / orig_height)
                    new_width = orig_width * ratio
                    new_height = orig_height * ratio
                    logo = Image(logo_abspath, width=new_width, height=new_height)
                except Exception as e:
                    logger.error(f"Error cargando logo: {e}")
                    logo = ""
            else:
                logo = ""

            # Datos de empresa (sin direcciones ni 'OBLIGADO A LLEVAR CONTABILIDAD')
            razon_social = getattr(opciones, 'razon_social', '') or getattr(proforma.empresa, 'razon_social', '')
            identificacion_val = getattr(opciones, 'identificacion', '') or getattr(proforma.empresa, 'ruc', '')
            contribuyente_especial = getattr(opciones, 'contribuyente_especial', '') if hasattr(opciones, 'contribuyente_especial') else ''
            agente_retencion = getattr(opciones, 'agente_retencion', '') if hasattr(opciones, 'agente_retencion') else ''

            datos_empresa_lineas = []
            if identificacion_val:
                datos_empresa_lineas.append(f"<b>RUC:</b> {identificacion_val}")
            datos_empresa_lineas.append(f"<b>{razon_social}</b>")
            if contribuyente_especial:
                datos_empresa_lineas.append(f"<b>Contribuyente Especial Nro</b> {contribuyente_especial}")
            if agente_retencion:
                datos_empresa_lineas.append(f"<b>Agente de Retención Resolución No.</b> {agente_retencion}")
            datos_empresa = "<br/>".join(datos_empresa_lineas)
            datos_empresa_paragraph = Paragraph(datos_empresa, self.styles['DatosEmpresa'])

            ANCHO_SUPERIOR = 195  # mm
            ESPACIO_ENTRE = 8     # mm
            ANCHO_COLUMNA = (ANCHO_SUPERIOR - ESPACIO_ENTRE) / 2
            ANCHO_TOTAL_TABLA = ANCHO_SUPERIOR  # <-- Este es el ancho que usarás para las tablas inferiores

            # Columna izquierda: SOLO logo (como el mock)
            columna_izq = Table(
                [[logo]],
                colWidths=[ANCHO_COLUMNA*mm]
            )
            columna_izq.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))

            # === CUADRO DE INFORMACIÓN PROFORMA - LIMPIO Y CENTRADO ===
            identificacion_val = getattr(opciones, 'identificacion', '') or getattr(proforma.empresa, 'ruc', '')
            numero = getattr(proforma, 'numero', getattr(proforma, 'id', ''))
            fecha_emi = getattr(proforma, 'fecha_emision', None) or datetime.now()
            fecha_venc = getattr(proforma, 'fecha_vencimiento', None)
            try:
                validez = (fecha_venc - fecha_emi).days if (fecha_emi and fecha_venc) else None
            except Exception:
                validez = None

            # 1. Encabezado "PROFORMA 2022 - 87656"
            encabezado = Paragraph(f"PROFORMA {fecha_emi.strftime('%Y')} - {numero}", self.styles['EncabezadoLimpio'])

            # 2. Datos organizados (solo fecha y vencimiento)
            datos_info = [
                ['Fecha:', fecha_emi.strftime('%d/%m/%Y')],
                ['Vencimiento:', fecha_venc.strftime('%d/%m/%Y') if fecha_venc else '-'],
            ]

            # Crear tabla de datos simple y limpia
            tabla_datos_simple = []
            for etiqueta, valor in datos_info:
                tabla_datos_simple.append([
                    Paragraph(f'<b>{etiqueta}</b>', self.styles['EtiquetaLimpia']),
                    Paragraph(str(valor), self.styles['ValorLimpio'])
                ])

            tabla_datos_info = Table(tabla_datos_simple, colWidths=[35*mm, 55*mm])
            tabla_datos_info.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ]))

            # ENSAMBLAR CUADRO DERECHO LIMPIO: empresa arriba, luego encabezado y datos
            tabla_cuadro_limpio = Table([
                [datos_empresa_paragraph],
                [encabezado],
                [tabla_datos_info],
            ], colWidths=[ANCHO_COLUMNA*mm])
            
            tabla_cuadro_limpio.setStyle(TableStyle([
                # Sin marco exterior
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0,2), (-1,2), 'LEFT'),
                ('ALIGN', (0,0), (0,0), 'RIGHT'),  # datos empresa a la derecha
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0,2), (0,2), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))

            # SOLO PARA LOS DOS CUADROS SUPERIORES
            tabla_superior = Table(
                [[columna_izq, '', tabla_cuadro_limpio]],  # columna vacía en medio
                colWidths=[ANCHO_COLUMNA*mm, ESPACIO_ENTRE*mm, ANCHO_COLUMNA*mm]
            )
            tabla_superior.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            elementos.append(tabla_superior)
            # Agregar espacio extra antes de la tabla de cliente
            elementos.append(Spacer(1, 10*mm))

            # === DATOS DEL CLIENTE ===
            cliente = getattr(proforma, 'cliente', None)
            cliente_nombre = getattr(cliente, 'razon_social', getattr(cliente, 'nombres', ''))
            cliente_ident = getattr(cliente, 'identificacion', '')
            cliente_dir = getattr(cliente, 'direccion', '')
            cliente_email = getattr(cliente, 'correo', '')
            cliente_telefono = getattr(cliente, 'telefono', '')
            cliente_data = [
                [Paragraph('<b>Cliente</b>', self.styles['Campo']), Paragraph('', self.styles['Campo'])],
                [Paragraph(f'<b>Razón Social / Nombres y Apellidos:</b> {cliente_nombre}', self.styles['Campo']),
                 Paragraph(f'<b>Identificación:</b> {cliente_ident}', self.styles['Campo'])],
                [Paragraph(f'<b>Fecha de Emisión:</b> {(getattr(proforma, "fecha_emision", None) or datetime.now()).strftime("%d/%m/%Y")}', self.styles['Campo']),
                 Paragraph('', self.styles['Campo'])],
                [Paragraph(f'<b>Dirección:</b> {cliente_dir}', self.styles['Campo']),
                 Paragraph(f'<b>Email:</b> {cliente_email}', self.styles['Campo'])],
                [Paragraph(f'<b>Teléfono:</b> {cliente_telefono}', self.styles['Campo']),
                 Paragraph('', self.styles['Campo'])]
            ]
            # Ejemplo para la tabla de cliente
            tabla_cliente = Table(cliente_data, colWidths=[ANCHO_TOTAL_TABLA*0.5*mm, ANCHO_TOTAL_TABLA*0.5*mm])

            tabla_cliente.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                #('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elementos.append(tabla_cliente)
            # Separar tabla de productos
            elementos.append(Spacer(1, 6*mm))

            # === TABLA DE ÍTEMS PROFORMA ===
            headers = [
                Paragraph('<b>Concepto</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Cantidad</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Precio</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Subtotal</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Impuesto</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Total</b>', self.styles['CabeceraBlanca'])
            ]
            tabla_data = [headers]
            for detalle in detalles:
                # Concepto/Descripción
                descripcion = getattr(detalle, 'descripcion', None)
                if not descripcion:
                    if getattr(detalle, 'producto', None):
                        descripcion = getattr(detalle.producto, 'descripcion', '')
                    elif getattr(detalle, 'servicio', None):
                        descripcion = getattr(detalle.servicio, 'descripcion', '')
                    else:
                        descripcion = str(detalle)

                # Cantidad
                cantidad_val = float(getattr(detalle, 'cantidad', 1))
                cantidad = f"{cantidad_val:.0f}" if cantidad_val.is_integer() else f"{cantidad_val:.2f}"

                # Precio unitario y descuento
                precio_unitario_val = float(getattr(detalle, 'precio_unitario', getattr(detalle, 'precio', 0.0)))
                descuento_val = float(getattr(detalle, 'descuento', 0.0))
                precio_unitario = self._fmt_num(precio_unitario_val, 2)

                # Subtotal sin IVA
                subtotal = (precio_unitario_val * cantidad_val) - descuento_val
                subtotal_fmt = self._fmt_num(subtotal, 2)

                # Impuesto: intentar encontrar porcentaje en el detalle
                iva_pct = None
                for attr in ('porcentaje_iva', 'iva_porcentaje', 'iva', 'tarifa_iva'):
                    if hasattr(detalle, attr):
                        try:
                            iva_pct = float(getattr(detalle, attr))
                            break
                        except Exception:
                            pass
                impuesto_text = f"{int(iva_pct)}%" if iva_pct is not None else ''

                # Total por línea (igual al subtotal en el mock)
                precio_total = subtotal_fmt

                fila = [
                    Paragraph(str(descripcion), self.styles['Campo']),
                    Paragraph(str(cantidad), self.styles['Campo']),
                    Paragraph(str(precio_unitario), self.styles['NumericoDecimals']),
                    Paragraph(str(subtotal_fmt), self.styles['NumericoDecimals']),
                    Paragraph(impuesto_text, self.styles['Campo']),
                    Paragraph(str(precio_total), self.styles['NumericoDecimals'])
                ]
                tabla_data.append(fila)
            # Ejemplo para la tabla de productos
            ancho_tabla = ANCHO_TOTAL_TABLA * mm
            tabla_productos = Table(tabla_data, colWidths=[
                ancho_tabla*0.44, ancho_tabla*0.10,
                ancho_tabla*0.12, ancho_tabla*0.12,
                ancho_tabla*0.10, ancho_tabla*0.12
            ])
            tabla_productos.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Concepto alineado a la izquierda
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Números a la derecha
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elementos.append(tabla_productos)
            # Separar tabla de totales/información adicional
            elementos.append(Spacer(1, 6*mm))

            # === INFORMACIÓN + TOTALES ===
            # Obtener datos del proformador y empresa
            facturador_nombre = getattr(proforma, 'facturador', None)
            if facturador_nombre:
                facturador_nombre = facturador_nombre.nombres
            else:
                facturador_nombre = 'N/A'
            
            # Obtener configuración de empresa
            from inventario.models import Opciones
            empresa_config = Opciones.objects.first()
            empresa_telefono = getattr(empresa_config, 'telefono', 'N/A') if empresa_config else 'N/A'
            empresa_correo = getattr(empresa_config, 'correo', 'N/A') if empresa_config else 'N/A'
            
            info_adicional = f"""
            <b>Información</b><br/>
            Vendedor: {facturador_nombre}<br/>
            Teléfono: {empresa_telefono}<br/>
            Correo: {empresa_correo}
            """

            # --- TOTALES ---
            totales_labels = []
            totales_values = []

            # Subtotales por tarifa de IVA y otros impuestos
            subtotales = {}
            ivas = {}

            # Si la proforma tiene desglose de impuestos en modelo relacionado, se puede completar aquí.

            # Subtotales especiales (solo si existen y son > 0)
            # Subtotales especiales si existieran en Proforma (ajustar según tu modelo)

            # Subtotal global
            if hasattr(proforma, 'subtotal') and getattr(proforma, 'subtotal') is not None:
                totales_labels.append('Subtotal')
                totales_values.append(self._fmt_num(getattr(proforma, 'subtotal', 0.0), 2))

            # Descuento (solo si existe)
            if getattr(proforma, 'total_descuento', 0.0) > 0:
                totales_labels.append('DESCUENTO')
                totales_values.append(f"{getattr(proforma, 'total_descuento', 0.0):.2f}")

            # ICE (si existiera una relación de impuestos en proforma; omitir por defecto)

            # Impuestos totales provenientes de la proforma con posible tasa
            iva_pct_unico = None
            try:
                tasas = set()
                for d in detalles:
                    for attr in ('porcentaje_iva', 'iva_porcentaje', 'iva', 'tarifa_iva'):
                        if hasattr(d, attr) and getattr(d, attr) not in (None, ''):
                            tasas.add(float(getattr(d, attr)))
                            break
                if len(tasas) == 1:
                    iva_pct_unico = int(list(tasas)[0])
            except Exception:
                iva_pct_unico = None

            if getattr(proforma, 'total_impuestos', 0.0) > 0:
                label_imp = f"Impuesto {iva_pct_unico}%" if iva_pct_unico is not None else 'Impuestos'
                totales_labels.append(label_imp)
                totales_values.append(self._fmt_num(getattr(proforma, 'total_impuestos', 0.0), 2))

            # Valor total (siempre)
            totales_labels.append('Total')
            totales_values.append(self._fmt_num(getattr(proforma, 'total', 0.0), 2))

            totales_text = '<br/>'.join(totales_labels)
            valores_text = '<br/>'.join(totales_values)
            fila_inferior = [
                Paragraph(info_adicional, self.styles['Campo']),
                Paragraph(totales_text, self.styles['Campo']),
                Paragraph(valores_text, self.styles['NumericoDecimals'])
            ]
            # Ejemplo para la tabla de totales/información adicional
            tabla_inferior = Table([fila_inferior], colWidths=[
                ancho_tabla*0.33, ancho_tabla*0.46, ancho_tabla*0.21
            ])
            tabla_inferior.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                # ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
            ]))
            elementos.append(tabla_inferior)
            # Separación
            elementos.append(Spacer(1, 6*mm))

            # Mensaje de pago sugerido, centrado
            try:
                msg_dias = validez if validez is not None else 30
            except Exception:
                msg_dias = 30
            tbl_pago = Table([[Paragraph(f"Pagar antes de {msg_dias} días", self.styles['Campo'])]], colWidths=[ancho_tabla])
            tbl_pago.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER')
            ]))
            elementos.append(tbl_pago)

            # Cuenta bancaria centrada si existe
            cuenta_bancaria = None
            for attr in ('cuenta_bancaria', 'bank_account', 'numero_cuenta', 'cuenta'):
                if hasattr(opciones, attr):
                    val = getattr(opciones, attr)
                    if val:
                        cuenta_bancaria = val
                        break
            if cuenta_bancaria:
                elementos.append(Spacer(1, 2*mm))
                tbl_bank = Table([[Paragraph(f"Bank Account: {cuenta_bancaria}", self.styles['Campo'])]], colWidths=[ancho_tabla])
                tbl_bank.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER')
                ]))
                elementos.append(tbl_bank)

            # Nota/observaciones (opcional)
            observ = getattr(proforma, 'observaciones', '')
            if observ:
                elementos.append(Spacer(1, 4))
                observacion_table = Table([[Paragraph(observ, self.styles['Campo'])]], colWidths=[ancho_tabla])
                observacion_table.setStyle(TableStyle([
                    ('LEFTPADDING', (0, 0), (-1, -1), 2),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('FONTSIZE', (0, 0), (-1, -1), 7),
                ]))
                elementos.append(observacion_table)

            doc.build(elementos)
            logger.info(f"PROFORMA generada exitosamente: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generando PROFORMA: {e}")
            raise

    def generar_ride_proforma_file(self, proforma, output_dir=None):
        """Genera el PDF de PROFORMA y devuelve la ruta del archivo."""
        from inventario.models import Opciones

        # Detalles
        detalles = getattr(proforma, 'detalles', None)
        if hasattr(detalles, 'all'):
            detalles = detalles.all()
        else:
            detalles = []

        # Opciones por empresa
        opciones = Opciones.objects.filter(empresa=getattr(proforma, 'empresa', None)).first() or Opciones.objects.first()

        # Salida
        if output_dir is None:
            output_dir = os.path.join(settings.MEDIA_ROOT, 'ride')
        os.makedirs(output_dir, exist_ok=True)

        numero = getattr(proforma, 'numero', None) or f"{getattr(proforma, 'id', 0)}"
        filename = f"PROFORMA_{numero}.pdf"
        output_path = os.path.join(output_dir, filename)

        return self.generar_ride_proforma(proforma, detalles, opciones, output_path)

    def _obtener_descripcion_forma_pago(self, codigo_sri):
        """Obtiene la descripción oficial de la forma de pago.

        La información se toma directamente de ``FormaPago.FORMAS_PAGO_CHOICES``
        (tabla 24 del SRI) para evitar mantener mapas duplicados o
        desactualizados.
        """
        # Importar aquí para evitar problemas de importación antes de que
        # Django esté configurado
        from inventario.models import FormaPago

        descripciones = dict(FormaPago.FORMAS_PAGO_CHOICES)
        descripcion = descripciones.get(codigo_sri)
        if descripcion is None:
            logger.warning(
                f"Código de forma de pago no contemplado: {codigo_sri}"
            )
            return codigo_sri
        return descripcion
