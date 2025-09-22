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
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from xml.etree import ElementTree as ET
import re
import logging

logger = logging.getLogger(__name__)

from inventario.utils.media_paths import build_proforma_media_paths

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
        self.styles.add(ParagraphStyle(
            name='CabeceraBlanca',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold',
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceAfter=0
        ))
        # Encabezado limpio (sin negrita) para tablas
        self.styles.add(ParagraphStyle(
            name='CabeceraLimpia',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceAfter=0
        ))
        self.styles.add(ParagraphStyle(
            name='DatosEmpresa',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            alignment=TA_RIGHT,
            spaceAfter=1,
            leading=10
        ))
        self.styles.add(ParagraphStyle(
            name='Campo',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            alignment=TA_LEFT,
            spaceAfter=0,
            leading=9
        ))
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
        self.styles.add(ParagraphStyle(
            name='EtiquetaLimpia',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=0,
            leading=9
        ))
        self.styles.add(ParagraphStyle(
            name='ValorLimpio',
            parent=self.styles['Normal'],
            fontSize=8,
            fontName='Helvetica',
            alignment=TA_LEFT,
            spaceAfter=0,
            leading=9
        ))
        self.styles.add(ParagraphStyle(
            name='NumericoDecimals',
            parent=self.styles['Normal'],
            fontSize=9,
            fontName='Helvetica',
            alignment=TA_RIGHT,
            spaceAfter=1
        ))
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

    def _parse_iva_pct(self, raw):
        """Devuelve el IVA como porcentaje (0..100) a partir de distintos formatos.

        Soporta: 12, '12', '12%', '12.00 %', '0.12', '0,12', 'IVA_12', '15%&'.
        Retorna None si no puede inferirlo.
        """
        if raw in (None, ""):
            return None
        # numérico directo
        if isinstance(raw, (int, float)):
            try:
                val = float(raw)
            except Exception:
                return None
            if 0 <= val <= 1:
                return val * 100.0
            if 1 < val <= 100:
                return val
            # fuera de rango típico, descartar
            return None
        # texto: extraer primer número
        try:
            s = str(raw).lower().replace(',', '.')
            # Si es un código SRI puro (solo dígitos), mapearlo primero
            if s.isdigit():
                mapped = self._map_codigo_iva_to_percent(s)
                if mapped is not None:
                    return mapped
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)", s)
            if not match:
                return None
            num = float(match.group(1))
            if 0 <= num <= 1:
                return num * 100.0
            if 1 < num <= 100:
                return num
            return None
        except Exception:
            return None

    def _map_codigo_iva_to_percent(self, code):
        """Mapea códigos SRI de IVA a porcentaje (0..100). Devuelve None si no coincide."""
        try:
            c = str(code).strip()
        except Exception:
            return None
        mapping = {
            '0': 0.0,   # 0%
            '2': 12.0,  # 12%
            '3': 14.0,  # 14% (histórico)
            '4': 15.0,  # 15% (actual)
            '5': 5.0,   # 5%
            '6': 0.0,   # No objeto de impuesto
            '7': 0.0,   # Exento de IVA
            '8': 8.0,   # 8% (diferenciado)
            '9': 15.0,  # 15% (normalizado, antes 16%)
            '10': 13.0  # 13%
        }
        return mapping.get(c)

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
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
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

            # 2. Datos organizados (solo fecha)
            datos_info = [
                ['Fecha:', fecha_emi.strftime('%d/%m/%Y')],
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

            # === DATOS DEL CLIENTE (compacto, una sola columna de valores) ===
            cliente = getattr(proforma, 'cliente', None)
            cliente_nombre = getattr(cliente, 'razon_social', getattr(cliente, 'nombres', ''))
            cliente_ident = getattr(cliente, 'identificacion', '')
            cliente_dir = getattr(cliente, 'direccion', '')
            # Email del cliente (con fallback a 'email')
            cliente_email = getattr(cliente, 'correo', '') or getattr(cliente, 'email', '')
            # Unir posibles teléfonos en una sola línea
            tels = []
            for tel_attr in ('telefono', 'celular', 'telefono_secundario', 'movil'):
                if hasattr(cliente, tel_attr):
                    val = getattr(cliente, tel_attr)
                    if val:
                        tels.append(str(val))
            cliente_telefonos = ' '.join(dict.fromkeys(tels))  # quitar duplicados preservando orden
            fecha_emision_text = (getattr(proforma, 'fecha_emision', None) or datetime.now()).strftime('%d/%m/%Y')

            etiqueta_style = self.styles['Campo']
            valor_style = self.styles['Campo']

            cliente_rows = [
                [Paragraph('<b>Cliente:</b>', etiqueta_style), Paragraph(cliente_nombre or '', valor_style)],
                [Paragraph('<b>RUC:</b>', etiqueta_style), Paragraph(cliente_ident or '', valor_style)],
                [Paragraph('<b>Direccion:</b>', etiqueta_style), Paragraph(cliente_dir or '', valor_style)],
                [Paragraph('<b>Email:</b>', etiqueta_style), Paragraph(cliente_email or '', valor_style)],
                [Paragraph('<b>Telefonos:</b>', etiqueta_style), Paragraph(cliente_telefonos or '', valor_style)],
                [Paragraph('<b>Fecha:</b>', etiqueta_style), Paragraph(fecha_emision_text, valor_style)],
            ]

            # Tabla de cliente compacta: 2 columnas (etiqueta/valor)
            etiqueta_col_mm = 30
            tabla_cliente = Table(
                cliente_rows,
                colWidths=[etiqueta_col_mm*mm, (ANCHO_TOTAL_TABLA - etiqueta_col_mm)*mm]
            )

            tabla_cliente.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),  # etiquetas a la derecha
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),   # valores a la izquierda
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elementos.append(tabla_cliente)
            # Separar tabla de productos
            elementos.append(Spacer(1, 6*mm))

            # === TABLA DE ÍTEMS PROFORMA ===
            headers = [
                Paragraph('Descripción', self.styles['CabeceraLimpia']),
                Paragraph('Cantidad', self.styles['CabeceraLimpia']),
                Paragraph('Precio', self.styles['CabeceraLimpia']),
                Paragraph('IVA', self.styles['CabeceraLimpia']),
                Paragraph('Desc.', self.styles['CabeceraLimpia']),
                Paragraph('Total', self.styles['CabeceraLimpia'])
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

                # Base imponible (después de descuento)
                base_val = (precio_unitario_val * cantidad_val) - descuento_val
                if base_val < 0:
                    base_val = 0.0

                # IVA: obtener porcentaje con parser robusto
                iva_pct = None
                for attr in ('porcentaje_iva', 'iva_porcentaje', 'iva', 'tarifa_iva'):
                    if hasattr(detalle, attr):
                        raw = getattr(detalle, attr)
                        if raw in (None, ''):
                            continue
                        # Si la propiedad es 'iva', puede ser código SRI: mapear primero
                        if attr == 'iva':
                            iva_pct = self._map_codigo_iva_to_percent(raw)
                            if iva_pct is None:
                                iva_pct = self._parse_iva_pct(raw)
                        else:
                            iva_pct = self._parse_iva_pct(raw)
                        if iva_pct is not None:
                            break
                # Fallback: tomar IVA desde el producto/servicio si no está en el detalle
                if iva_pct is None:
                    for origen in (getattr(detalle, 'producto', None), getattr(detalle, 'servicio', None)):
                        if origen is None:
                            continue
                        # Método helper del modelo si existe
                        if hasattr(origen, 'get_porcentaje_iva_real'):
                            try:
                                val = getattr(origen, 'get_porcentaje_iva_real')()
                                if val is not None:
                                    iva_pct = float(val)
                                    if iva_pct is not None:
                                        break
                            except Exception:
                                pass
                        # Atributos comunes
                        for attr in ('porcentaje_iva', 'iva_porcentaje', 'iva', 'tarifa_iva', 'porcentaje'):
                            if hasattr(origen, attr):
                                raw = getattr(origen, attr)
                                if raw in (None, ''):
                                    continue
                                if attr == 'iva':
                                    iva_pct = self._map_codigo_iva_to_percent(raw)
                                    if iva_pct is None:
                                        iva_pct = self._parse_iva_pct(raw)
                                else:
                                    iva_pct = self._parse_iva_pct(raw)
                                if iva_pct is not None:
                                    break
                        if iva_pct is not None:
                            break
                # Convertir a tasa
                iva_rate = (iva_pct or 0.0) / 100.0

                iva_monto_val = base_val * iva_rate
                total_val = base_val + iva_monto_val

                iva_monto = self._fmt_num(iva_monto_val, 2)
                # Mostrar en columna IVA el porcentaje configurado (del detalle o del producto/servicio)
                iva_display_pct = iva_pct or 0.0
                if float(int(round(iva_display_pct))) == float(round(iva_display_pct)):
                    iva_display = f"{int(round(iva_display_pct))}%"
                else:
                    iva_display = f"{iva_display_pct:.2f}%"
                desc_fmt = self._fmt_num(descuento_val, 2)
                total_fmt = self._fmt_num(total_val, 2)

                fila = [
                    Paragraph(str(descripcion), self.styles['Campo']),
                    Paragraph(str(cantidad), self.styles['Campo']),
                    Paragraph(str(precio_unitario), self.styles['NumericoDecimals']),
                    Paragraph(str(iva_display), self.styles['Campo']),
                    Paragraph(str(desc_fmt), self.styles['NumericoDecimals']),
                    Paragraph(str(total_fmt), self.styles['NumericoDecimals'])
                ]
                tabla_data.append(fila)
            # Ejemplo para la tabla de productos
            ancho_tabla = ANCHO_TOTAL_TABLA * mm
            tabla_productos = Table(tabla_data, colWidths=[
                ancho_tabla*0.46, ancho_tabla*0.10,
                ancho_tabla*0.12, ancho_tabla*0.10,
                ancho_tabla*0.10, ancho_tabla*0.12
            ])
            tabla_productos.setStyle(TableStyle([
                # Encabezado sin fondo gris y tipografía más agradable
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                # Tamaño de letra más grande para el encabezado
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Concepto alineado a la izquierda
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Números a la derecha
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Solo líneas superiores para un look limpio
                ('LINEABOVE', (0, 0), (-1, 0), 0.6, colors.black),  # línea superior del header
                ('LINEABOVE', (0, 1), (-1, -1), 0.25, colors.black),  # línea superior para cada fila
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elementos.append(tabla_productos)
            # Separar tabla de totales/información adicional
            elementos.append(Spacer(1, 6*mm))

            # === INFORMACIÓN + TOTALES ===
            # Datos del vendedor (facturador) con robustos fallbacks
            facturador = getattr(proforma, 'facturador', None)
            # Nombre
            if facturador:
                nombre_partes = []
                for attr in ('nombres', 'nombre', 'first_name'):
                    if hasattr(facturador, attr) and getattr(facturador, attr):
                        nombre_partes.append(str(getattr(facturador, attr)))
                        break
                for attr in ('apellidos', 'apellido', 'last_name'):
                    if hasattr(facturador, attr) and getattr(facturador, attr):
                        nombre_partes.append(str(getattr(facturador, attr)))
                        break
                if not nombre_partes and hasattr(facturador, 'get_full_name'):
                    try:
                        full = facturador.get_full_name()
                        if full:
                            nombre_partes = [full]
                    except Exception:
                        pass
                facturador_nombre = ' '.join(nombre_partes).strip() or str(facturador)
            else:
                facturador_nombre = 'N/A'

            # Teléfono del vendedor
            facturador_telefono = None
            if facturador:
                for tel_attr in ('telefono', 'celular', 'movil', 'phone', 'telefono1', 'telefono2'):
                    if hasattr(facturador, tel_attr):
                        val = getattr(facturador, tel_attr)
                        if val:
                            facturador_telefono = str(val)
                            break

            # Correo del vendedor
            facturador_correo = None
            if facturador:
                for mail_attr in ('correo', 'email'):
                    if hasattr(facturador, mail_attr):
                        val = getattr(facturador, mail_attr)
                        if val:
                            facturador_correo = str(val)
                            break
                # Fallback: usuario o user relacionado
                if not facturador_correo:
                    for rel in ('usuario', 'user'):
                        if hasattr(facturador, rel):
                            user_obj = getattr(facturador, rel)
                            if hasattr(user_obj, 'email') and getattr(user_obj, 'email'):
                                facturador_correo = str(getattr(user_obj, 'email'))
                                break

            # Fallback a datos de empresa si faltan teléfono/correo del vendedor
            from inventario.models import Opciones
            empresa = getattr(proforma, 'empresa', None)
            empresa_config = Opciones.objects.for_tenant(empresa).first()
            if not empresa_config and empresa:
                empresa_config = Opciones.objects.create(empresa=empresa, identificacion=getattr(empresa, 'ruc', '0000000000000'))
            empresa_telefono = getattr(empresa_config, 'telefono', None) if empresa_config else None
            empresa_correo = getattr(empresa_config, 'correo', None) if empresa_config else None

            telefono_info = facturador_telefono or empresa_telefono or 'N/A'
            correo_info = facturador_correo or empresa_correo or 'N/A'

            info_adicional = f"""
            <b>Información</b><br/>
            Vendedor: {facturador_nombre}<br/>
            Teléfono: {telefono_info}<br/>
            Correo: {correo_info}
            """

            # --- TOTALES (desglose como en la imagen) ---
            totales_labels = []
            totales_values = []

            if detalles:
                subtotal_bruto = 0.0
                total_desc = 0.0
                subtotal_cero = 0.0
                subtotal_gravado = 0.0
                iva_breakdown = {}

                for d in detalles:
                    try:
                        qty = float(getattr(d, 'cantidad', 1) or 1)
                    except Exception:
                        qty = 1.0
                    try:
                        pu = float(getattr(d, 'precio_unitario', getattr(d, 'precio', 0.0)) or 0.0)
                    except Exception:
                        pu = 0.0
                    try:
                        desc = float(getattr(d, 'descuento', 0.0) or 0.0)
                    except Exception:
                        desc = 0.0

                    base_linea = max(0.0, (qty * pu) - desc)
                    subtotal_bruto += (qty * pu)
                    total_desc += desc

                    # tasa IVA
                    pct = None
                    for attr in ('porcentaje_iva', 'iva_porcentaje', 'iva', 'tarifa_iva'):
                        if hasattr(d, attr):
                            raw = getattr(d, attr)
                            if raw in (None, ''):
                                continue
                            if attr == 'iva':
                                pct = self._map_codigo_iva_to_percent(raw)
                                if pct is None:
                                    pct = self._parse_iva_pct(raw)
                            else:
                                pct = self._parse_iva_pct(raw)
                            if pct is not None:
                                break
                    if pct is None:
                        for origen in (getattr(d, 'producto', None), getattr(d, 'servicio', None)):
                            if origen is None:
                                continue
                            if hasattr(origen, 'get_porcentaje_iva_real'):
                                try:
                                    val = getattr(origen, 'get_porcentaje_iva_real')()
                                    if val is not None:
                                        pct = float(val)
                                except Exception:
                                    pct = None
                            if pct is None:
                                for attr in ('porcentaje_iva', 'iva_porcentaje', 'iva', 'tarifa_iva', 'porcentaje'):
                                    if hasattr(origen, attr):
                                        raw = getattr(origen, attr)
                                        if raw in (None, ''):
                                            continue
                                        if attr == 'iva':
                                            pct = self._map_codigo_iva_to_percent(raw)
                                            if pct is None:
                                                pct = self._parse_iva_pct(raw)
                                        else:
                                            pct = self._parse_iva_pct(raw)
                                        if pct is not None:
                                            break
                            if pct is not None:
                                break

                    tasa = (pct or 0.0) / 100.0
                    if tasa == 0.0:
                        subtotal_cero += base_linea
                    else:
                        subtotal_gravado += base_linea
                        iva_breakdown[pct or 0.0] = iva_breakdown.get(pct or 0.0, 0.0) + (base_linea * tasa)

                subtotal_neto = max(0.0, subtotal_bruto - total_desc)

                # Armar líneas
                totales_labels.extend(['SUBTOTAL', 'DESCUENTO', 'SUBTOTAL NETO', 'SUBTOTAL 0%', 'SUBTOTAL IVA'])
                totales_values.extend([
                    self._fmt_num(subtotal_bruto, 2),
                    self._fmt_num(total_desc, 2),
                    self._fmt_num(subtotal_neto, 2),
                    self._fmt_num(subtotal_cero, 2),
                    self._fmt_num(subtotal_gravado, 2),
                ])

                # Asegurar que existan 5% y 15% en el desglose
                for fijo in (5.0, 15.0):
                    iva_breakdown.setdefault(fijo, 0.0)
                # Ordenar por porcentaje
                for key in sorted(iva_breakdown.keys()):
                    etiqueta = f"IVA {int(key) if float(int(key)) == float(key) else key} %"
                    totales_labels.append(etiqueta)
                    totales_values.append(self._fmt_num(iva_breakdown[key], 2))

                total_general = subtotal_neto + sum(iva_breakdown.values())
                totales_labels.append('TOTAL')
                totales_values.append(self._fmt_num(total_general, 2))
            else:
                # Fallback a campos de proforma si no hay detalles
                totales_labels.append('Subtotal')
                totales_values.append(self._fmt_num(getattr(proforma, 'subtotal', 0.0), 2))
                if getattr(proforma, 'total_descuento', 0.0) is not None:
                    totales_labels.append('DESCUENTO')
                    totales_values.append(self._fmt_num(getattr(proforma, 'total_descuento', 0.0), 2))
                if getattr(proforma, 'total_impuestos', 0.0) is not None:
                    totales_labels.append('Impuestos')
                    totales_values.append(self._fmt_num(getattr(proforma, 'total_impuestos', 0.0), 2))
                totales_labels.append('TOTAL')
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
                # Solo línea superior para separar la sección de totales
                ('LINEABOVE', (0, 0), (-1, 0), 0.6, colors.black),
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
            pdf_bytes = buffer.getvalue()
            default_storage.delete(output_path)
            saved_path = default_storage.save(output_path, ContentFile(pdf_bytes))
            logger.info(f"PROFORMA generada exitosamente: {saved_path}")
            return saved_path
            
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
        empresa = getattr(proforma, 'empresa', None)
        opciones = Opciones.objects.for_tenant(empresa).first()
        if not opciones and empresa:
            opciones = Opciones.objects.create(empresa=empresa, identificacion=getattr(empresa, 'ruc', '0000000000000'))

        # Salida
        media_paths = build_proforma_media_paths(proforma)

        target_dir = output_dir or media_paths.pdf_dir
        numero = getattr(proforma, 'numero', None) or f"{getattr(proforma, 'id', 0)}"
        filename = f"PROFORMA_{numero}.pdf"
        output_path = f"{target_dir}/{filename}"

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
