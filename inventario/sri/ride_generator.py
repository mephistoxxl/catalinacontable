# inventario/ride_generator.py

import os
import base64
import qrcode
import tempfile
from io import BytesIO
from datetime import datetime, timedelta
from pathlib import Path
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from xml.etree import ElementTree as ET
import logging

logger = logging.getLogger(__name__)

from inventario.utils.media_paths import build_factura_media_paths

class RIDEGenerator:
    """
    Generador de RIDE (Representación Impresa del Documento Electrónico)
    para comprobantes electrónicos de Ecuador según especificaciones del SRI
    """
    
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
        
        # Estilo para datos de empresa
        self.styles.add(ParagraphStyle(
            name='DatosEmpresa',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica',
            alignment=TA_CENTER,
            spaceAfter=2
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
            fontSize=15,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=2,
            leading=17
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

    def generar_ride_factura(self, factura, detalles, opciones, output_path, logo_path=None, clave_acceso=None):
        """Generar RIDE para factura con diseño exacto del SRI y datos reales"""
        try:
            from reportlab.graphics.barcode import code128
            from reportlab.platypus import Spacer
            logger.info(f"Generando RIDE para factura {factura.id}")
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
            # Logo - Compatible con filesystem local Y storage remoto (S3)
            logo = ""
            if hasattr(opciones, 'imagen') and opciones.imagen:
                try:
                    from reportlab.lib.utils import ImageReader
                    # BytesIO ya está importado al inicio del archivo
                    
                    # Intentar leer desde storage (funciona con filesystem y S3)
                    with opciones.imagen.open('rb') as logo_file:
                        logo_data = BytesIO(logo_file.read())
                    
                    reader = ImageReader(logo_data)
                    orig_width, orig_height = reader.getSize()
                    max_width = 45 * mm
                    max_height = 40 * mm
                    ratio = min(max_width / orig_width, max_height / orig_height)
                    new_width = orig_width * ratio
                    new_height = orig_height * ratio
                    
                    # Resetear el BytesIO para leerlo de nuevo
                    logo_data.seek(0)
                    logo = Image(logo_data, width=new_width, height=new_height)
                    logger.info(f"✅ Logo cargado correctamente: {opciones.imagen.name}")
                except Exception as e:
                    logger.error(f"❌ Error cargando logo: {e}")
                    logo = ""
            else:
                logger.warning("⚠️ No hay logo configurado en Opciones")

            # Datos de empresa
            # ✅ Mostrar RAZÓN SOCIAL y NOMBRE COMERCIAL (ambos en negrita)
            nombre_comercial = getattr(opciones, 'nombre_comercial', '')
            razon_social = getattr(opciones, 'razon_social', '')
            
            # Mostrar razón social arriba
            linea_razon_social = f"<b>{razon_social}</b><br/>" if razon_social else ""
            
            # Mostrar nombre comercial solo si es diferente y está configurado
            linea_nombre_comercial = ""
            if nombre_comercial and nombre_comercial != '[CONFIGURAR NOMBRE COMERCIAL]' and nombre_comercial != razon_social:
                linea_nombre_comercial = f"<b>{nombre_comercial}</b><br/>"
            
            dir_matriz = getattr(opciones, 'direccion_matriz', getattr(opciones, 'direccion_establecimiento', ''))
            dir_sucursal = getattr(opciones, 'direccion_establecimiento', '')
            contribuyente_especial = getattr(opciones, 'contribuyente_especial', '') if hasattr(opciones, 'contribuyente_especial') else ''
            obligado = getattr(opciones, 'obligado', 'NO')
            agente_retencion = getattr(opciones, 'agente_retencion', '') if hasattr(opciones, 'agente_retencion') else ''
            
            datos_empresa = f"""
{linea_razon_social}{linea_nombre_comercial}<b>Dirección Matriz:</b> {dir_matriz}<br/>
<b>Dirección Sucursal:</b> {dir_sucursal}<br/>
{'<b>Contribuyente Especial Nro</b> ' + contribuyente_especial + '<br/>' if contribuyente_especial else ''}
<b>OBLIGADO A LLEVAR CONTABILIDAD:</b> {obligado}<br/>
{f'<b>Agente de Retención Resolución No.</b> {agente_retencion}' if agente_retencion else ''}
"""
            datos_empresa_paragraph = Paragraph(datos_empresa, self.styles['DatosEmpresa'])

            ANCHO_SUPERIOR = 195  # mm
            ESPACIO_ENTRE = 8     # mm
            ANCHO_COLUMNA = (ANCHO_SUPERIOR - ESPACIO_ENTRE) / 2
            ANCHO_TOTAL_TABLA = ANCHO_SUPERIOR  # <-- Este es el ancho que usarás para las tablas inferiores

            cuadro_empresa = Table(
                [[datos_empresa_paragraph]],
                colWidths=[ANCHO_COLUMNA*mm]
            )
            cuadro_empresa.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            columna_izq = Table(
                [[logo], [Spacer(1, 2*mm)], [cuadro_empresa]],
                colWidths=[ANCHO_COLUMNA*mm],
                rowHeights=[40*mm, 2*mm, 35*mm]
            )
            columna_izq.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))

            # === CUADRO DE INFORMACIÓN - LIMPIO Y CENTRADO ===
            clave_acceso_factura = getattr(factura, 'clave_acceso', clave_acceso or '')
            numero_factura = f"{getattr(factura, 'establecimiento_formatted', getattr(factura, 'establecimiento', '001'))}-{getattr(factura, 'punto_emision_formatted', getattr(factura, 'punto_emision', '001'))}-{getattr(factura, 'secuencia_formatted', str(getattr(factura, 'secuencia', 1)).zfill(9))}"
            
            # ✅ CORREGIDO: Usar SOLO fecha_autorizacion (del SRI)
            # NUNCA usar fecha_emision como fecha de autorización (son conceptualmente diferentes)
            fecha_autorizacion_sri = getattr(factura, 'fecha_autorizacion', None)
            
            # 🔍 DEBUG: Log de la fecha de autorización
            logger.info(f"🔍 RIDE Generator - Factura #{factura.id}")
            logger.info(f"   fecha_autorizacion del objeto: {fecha_autorizacion_sri}")
            logger.info(f"   Tipo: {type(fecha_autorizacion_sri)}")
            logger.info(f"   Es None?: {fecha_autorizacion_sri is None}")
            
            # Formatear fecha de autorización
            if fecha_autorizacion_sri:
                # Fecha autorizada por el SRI (ajustada -5 horas para despliegue)
                fecha_aut_ajustada = fecha_autorizacion_sri - timedelta(hours=5)
                fecha_aut_val = fecha_aut_ajustada.strftime('%d/%m/%Y %H:%M:%S')
                logger.info(f"   ✅ Mostrará en RIDE (ajustada -5h): {fecha_aut_val}")
            else:
                # Factura NO autorizada aún
                fecha_aut_val = 'PENDIENTE DE AUTORIZACIÓN'
                logger.warning(f"   ⚠️ Mostrará en RIDE: {fecha_aut_val}")
            
            ambiente = getattr(opciones, 'ambiente_descripcion', self._obtener_ambiente(str(getattr(factura, 'ambiente', '2'))))
            emision = self._obtener_tipo_emision(str(getattr(factura, 'tipo_emision', '1')))
            identificacion_val = getattr(opciones, 'identificacion', '')

            # 1. ENCABEZADO "FACTURA" - LIMPIO
            encabezado_factura = Paragraph('FACTURA', self.styles['EncabezadoLimpio'])

            # 2. DATOS ORGANIZADOS EN BLOQUE SIMPLE
            datos_info = [
                ['R.U.C.:', identificacion_val],
                ['No.:', numero_factura], 
                ['NÚMERO DE AUTORIZACIÓN:', clave_acceso_factura],
                ['FECHA Y HORA DE AUTORIZACIÓN:', fecha_aut_val],
                ['AMBIENTE:', ambiente.capitalize()],
                ['EMISIÓN:', emision.capitalize()],
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

            # 3. CLAVE DE ACCESO Y CÓDIGO DE BARRAS - CENTRADO Y LIMPIO
            try:
                barcode = code128.Code128(clave_acceso_factura, barHeight=8*mm, barWidth=0.28*mm, humanReadable=False)
            except:
                barcode = Paragraph('Código de barras no disponible', self.styles['ClaveAcceso'])

            clave_titulo = Paragraph('<b>CLAVE DE ACCESO</b>', self.styles['EtiquetaLimpia'])
            clave_texto = Paragraph(clave_acceso_factura, self.styles['ClaveAcceso'])

            # Ajustar ancho del bloque para que quepa perfectamente en la columna
            bloque_clave = Table([
                [clave_titulo],
                [barcode],
                [clave_texto]
            ], colWidths=[80*mm])
            bloque_clave.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))

            # ENSAMBLAR TODO EL CUADRO LIMPIO - SIN BORDES INTERNOS
            tabla_cuadro_limpio = Table([
                [encabezado_factura],           # Fila 1: FACTURA
                [tabla_datos_info],             # Fila 2: Datos
                [bloque_clave]                  # Fila 3: Clave de acceso y barras
            ], colWidths=[ANCHO_COLUMNA*mm], rowHeights=[19*mm, 35*mm, 23*mm])
            
            tabla_cuadro_limpio.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.10, colors.black),  # Solo borde exterior
                ('ROUNDED', (0, 0), (-1, -1), 6),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0,1), (-1,1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0,1), (0,1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))

            # SOLO PARA LOS DOS CUADROS SUPERIORES
            tabla_superior = Table(
                [[columna_izq, '', tabla_cuadro_limpio]],  # columna vacía en medio
                colWidths=[ANCHO_COLUMNA*mm, ESPACIO_ENTRE*mm, ANCHO_COLUMNA*mm],
                rowHeights=[77*mm]
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
            cliente = getattr(factura, 'cliente', None)
            cliente_nombre = getattr(cliente, 'razon_social', getattr(cliente, 'nombres', ''))
            cliente_ident = getattr(cliente, 'identificacion', '')
            cliente_dir = getattr(cliente, 'direccion', '')
            cliente_email = getattr(cliente, 'correo', '')
            cliente_telefono = getattr(cliente, 'telefono', '')
            cliente_data = [
                [Paragraph(f'<b>Razón Social / Nombres y Apellidos:</b> {cliente_nombre}', self.styles['Campo']),
                 Paragraph(f'<b>Identificación:</b> {cliente_ident}', self.styles['Campo'])],
                [Paragraph(f'<b>Fecha de Emisión:</b> {(getattr(factura, "fecha_emision", None) or datetime.now()).strftime("%d/%m/%Y")}', self.styles['Campo']),
                 Paragraph(f'<b>Guía de Remisión:</b> {getattr(factura, "guia_remision", "")}', self.styles['Campo'])],
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
                ('BOX', (0, 0), (-1, -1), 0.10, colors.black),
                #('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elementos.append(tabla_cliente)
            # Separar tabla de productos
            elementos.append(Spacer(1, 6*mm))

            # === TABLA DE PRODUCTOS ===
            headers = [
                Paragraph('<b>Cod. Principal</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Cantidad</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>UND</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Descripción</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Precio Unitario</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Descuento</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Precio Total</b>', self.styles['CabeceraBlanca'])
            ]
            tabla_data = [headers]
            for detalle in detalles:
                cod_principal = getattr(detalle, 'codigo_principal', None)
                if not cod_principal:
                    if detalle.producto:
                        cod_principal = detalle.producto.codigo
                    elif detalle.servicio:
                        cod_principal = detalle.servicio.codigo

                cantidad = f"{getattr(detalle, 'cantidad', 1):.2f}"
                unidad = getattr(detalle, 'unidad_medida', 'UND')

                descripcion = getattr(detalle, 'descripcion', None)
                if not descripcion:
                    if detalle.producto:
                        descripcion = detalle.producto.descripcion
                    elif detalle.servicio:
                        descripcion = detalle.servicio.descripcion
                    else:
                        descripcion = str(detalle)

                precio_unitario = f"${getattr(detalle, 'precio_unitario', getattr(detalle, 'precio', 0.0)):.2f}"
                descuento = f"${getattr(detalle, 'descuento', 0.0):.2f}"
                # Calculate subtotal without IVA: (precio_unitario * cantidad) - descuento
                precio_unitario_val = float(getattr(detalle, 'precio_unitario', getattr(detalle, 'precio', 0.0)))
                cantidad_val = float(getattr(detalle, 'cantidad', 1))
                descuento_val = float(getattr(detalle, 'descuento', 0.0))
                subtotal = (precio_unitario_val * cantidad_val) - descuento_val
                precio_total = f"${subtotal:.2f}"
                fila = [
                    Paragraph(str(cod_principal), self.styles['Campo']),
                    Paragraph(str(cantidad), self.styles['Campo']),
                    Paragraph(str(unidad), self.styles['Campo']),
                    Paragraph(str(descripcion), self.styles['Campo']),
                    Paragraph(str(precio_unitario), self.styles['NumericoDecimals']),
                    Paragraph(str(descuento), self.styles['NumericoDecimals']),
                    Paragraph(str(precio_total), self.styles['NumericoDecimals'])
                ]
                tabla_data.append(fila)
            # Ejemplo para la tabla de productos
            ancho_tabla = ANCHO_TOTAL_TABLA * mm
            tabla_productos = Table(tabla_data, colWidths=[
                ancho_tabla*0.11, ancho_tabla*0.09, ancho_tabla*0.06,
                ancho_tabla*0.38, ancho_tabla*0.12, ancho_tabla*0.09, ancho_tabla*0.15
            ])
            tabla_productos.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (3, 1), (3, -1), 'LEFT'),
                ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOX', (0, 0), (-1, -1), 0.10, colors.black),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elementos.append(tabla_productos)
            # Separar tabla de totales/información adicional
            elementos.append(Spacer(1, 6*mm))

            # === INFORMACIÓN ADICIONAL + TOTALES ===
            # Obtener datos del facturador y empresa
            facturador_nombre = getattr(factura, 'facturador', None)
            if facturador_nombre:
                facturador_nombre = facturador_nombre.nombres
            else:
                facturador_nombre = 'N/A'
            
            # Obtener configuración de empresa
            from inventario.models import Opciones
            empresa = getattr(factura, 'empresa', None)
            empresa_config = Opciones.objects.for_tenant(empresa).first()
            if not empresa_config and empresa:
                empresa_config = Opciones.objects.create(empresa=empresa, identificacion=getattr(empresa, 'ruc', '0000000000000'))
            empresa_telefono = getattr(empresa_config, 'telefono', 'N/A') if empresa_config else 'N/A'
            empresa_correo = getattr(empresa_config, 'correo', 'N/A') if empresa_config else 'N/A'
            
            info_adicional = f"""
            <b>Información Adicional</b><br/>
            Sistema: Catalina Fact<br/>
            Vendedor: {facturador_nombre}<br/>
            Teléfono: {empresa_telefono}<br/>
            Correo: {empresa_correo}
            """

            # --- TOTALES DINÁMICOS E INTELIGENTES ---
            totales_labels = []
            totales_values = []

            # Subtotales por tarifa de IVA y otros impuestos
            subtotales = {}
            ivas = {}

            for ti in factura.totales_impuestos.all():
                if ti.codigo == '2':  # IVA
                    key = f"SUBTOTAL {float(ti.tarifa):.1f}%"
                    subtotales[key] = subtotales.get(key, 0) + float(ti.base_imponible)
                    iva_key = f"IVA {float(ti.tarifa):.1f}%"
                    ivas[iva_key] = ivas.get(iva_key, 0) + float(ti.valor)
                elif ti.codigo == '3':  # ICE
                    key = "ICE"
                    subtotales[key] = subtotales.get(key, 0) + float(ti.base_imponible)

            # Subtotales especiales (solo si existen y son > 0)
            if getattr(factura, 'subtotal_0', 0.0) > 0:
                subtotales['SUBTOTAL 0%'] = getattr(factura, 'subtotal_0', 0.0)
            if getattr(factura, 'subtotal_no_objeto_iva', 0.0) > 0:
                subtotales['SUBTOTAL No objeto de IVA'] = getattr(factura, 'subtotal_no_objeto_iva', 0.0)
            if getattr(factura, 'subtotal_exento_iva', 0.0) > 0:
                subtotales['SUBTOTAL EXENTO DE IVA'] = getattr(factura, 'subtotal_exento_iva', 0.0)
            if getattr(factura, 'subtotal_sin_impuestos', 0.0) > 0:
                subtotales['SUBTOTAL SIN IMPUESTOS'] = getattr(factura, 'subtotal_sin_impuestos', 0.0)

            # Agrega todos los subtotales encontrados (solo los que existen)
            for label, value in subtotales.items():
                if value > 0:
                    totales_labels.append(label)
                    totales_values.append(f"{value:.2f}")

            # Descuento (solo si existe)
            if getattr(factura, 'descuento', 0.0) > 0:
                totales_labels.append('DESCUENTO')
                totales_values.append(f"{getattr(factura, 'descuento', 0.0):.2f}")

            # ICE (solo si existe)
            ice_total = sum(float(ti.valor) for ti in factura.totales_impuestos.all() if ti.codigo == '3')
            if ice_total > 0:
                totales_labels.append('ICE')
                totales_values.append(f"{ice_total:.2f}")

            # IVAs presentes (solo los que existen)
            for label, value in ivas.items():
                if value > 0:
                    totales_labels.append(label)
                    totales_values.append(f"{value:.2f}")

            # Valor total (siempre)
            totales_labels.append('VALOR TOTAL')
            totales_values.append(f"{getattr(factura, 'total', 0.0):.2f}")

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
                ('BOX', (0, 0), (-1, -1), 0.10, colors.black),
                # ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
            ]))
            elementos.append(tabla_inferior)
            # Separar tabla de pagos
            elementos.append(Spacer(1, 6*mm))

            # === FORMA DE PAGO ===
            pago_headers = [
                Paragraph('<b>Forma de Pago</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Valor</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Plazo</b>', self.styles['CabeceraBlanca']),
                Paragraph('<b>Tiempo días</b>', self.styles['CabeceraBlanca'])
            ]
            
            # ✅ USAR RELACIÓN CORRECTA: formas_pago (no pagos)
            formas_pago = factura.formas_pago.all() if hasattr(factura, 'formas_pago') else None
            pago_data = [pago_headers]
            
            if formas_pago and formas_pago.exists():
                print(f"📋 RIDE: Procesando {formas_pago.count()} formas de pago")
                for forma_pago in formas_pago:
                    # Mapear códigos SRI a descripción legible
                    forma_descripcion = self._obtener_descripcion_forma_pago(forma_pago.forma_pago)
                    valor = f"${forma_pago.total:.2f}"
                    plazo = str(getattr(forma_pago, 'plazo', '0')) if getattr(forma_pago, 'plazo', None) is not None else '0'
                    tiempo_dias = str(getattr(forma_pago, 'unidad_tiempo', 'días')) if getattr(forma_pago, 'unidad_tiempo', None) is not None else 'días'
                    
                    pago_data.append([
                        Paragraph(forma_descripcion, self.styles['Campo']),
                        Paragraph(valor, self.styles['Campo']),
                        Paragraph(plazo, self.styles['Campo']),
                        Paragraph(tiempo_dias, self.styles['Campo'])
                    ])
                    print(f"  • {forma_descripcion}: {valor}")
            else:
                # ✅ Usar valor por defecto: SIN UTILIZACIÓN DEL SISTEMA FINANCIERO
                print("⚠️ RIDE: No se encontraron formas de pago, usando valor por defecto")
                pago_data.append([
                    Paragraph('SIN UTILIZACIÓN DEL SISTEMA FINANCIERO', self.styles['Campo']),
                    Paragraph(f"${factura.total:.2f}", self.styles['Campo']),
                    Paragraph('0', self.styles['Campo']),
                    Paragraph('días', self.styles['Campo'])
                ])
            # Ejemplo para la tabla de pagos
            tabla_pago = Table(pago_data, colWidths=[
                ancho_tabla*0.46, ancho_tabla*0.18, ancho_tabla*0.13, ancho_tabla*0.23
            ])
            tabla_pago.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOX', (0, 0), (-1, -1), 0.10, colors.black),
                #('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elementos.append(tabla_pago)
            # Separar tabla de observación
            elementos.append(Spacer(1, 6*mm))

            # === OBSERVACIÓN ===
            elementos.append(Spacer(1, 4))
            observacion_table = Table([['Observación']], colWidths=[ancho_tabla])
            observacion_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.10, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
            ]))
            elementos.append(observacion_table)

            doc.build(elementos)
            pdf_bytes = buffer.getvalue()
            logger.info(f"RIDE generado exitosamente: {output_path}")
            return pdf_bytes

        except Exception as e:
            logger.error(f"Error generando RIDE: {e}")
            raise

    def generar_ride_factura_firmado(self, factura, output_dir=None, firmar=False):
        """
        Genera el RIDE de una factura y opcionalmente lo firma electrónicamente.
        
        Args:
            factura: Instancia del modelo Factura
            output_dir (str, optional): Directorio de salida
            firmar (bool, optional): Si se debe firmar el PDF después de generarlo
        
        Returns:
            tuple: (ruta_pdf_generado, ruta_pdf_firmado) o solo ruta_pdf_generado si no se firma
        """
        # Obtener detalles y opciones necesarias
        from inventario.models import Opciones
        
        detalles = factura.detallefactura_set.all()
        empresa = getattr(factura, 'empresa', None)
        opciones = Opciones.objects.for_tenant(empresa).first()
        if not opciones and empresa:
            opciones = Opciones.objects.create(empresa=empresa, identificacion=getattr(empresa, 'ruc', '0000000000000'))
        
        media_paths = build_factura_media_paths(factura)

        # Generar nombre de archivo y ruta en almacenamiento
        target_dir = output_dir or media_paths.pdf_dir
        filename = f"RIDE_{factura.establecimiento}-{factura.punto_emision}-{str(factura.secuencia).zfill(9)}.pdf"
        storage_path = f"{target_dir}/{filename}"

        # 🔧 FIX CRÍTICO: SIEMPRE usar la clave de acceso ya generada de la factura
        # NUNCA generar nueva clave - debe existir desde la creación de la factura
        clave_acceso = getattr(factura, 'clave_acceso', None)

        if not clave_acceso:
            raise ValueError(f"Factura {factura.id} no tiene clave de acceso. "
                           f"La clave debe generarse al crear/guardar la factura.")
        
        logger.info(f"Generando RIDE para factura {factura.id} con clave: {clave_acceso}")
        
        # Generar el RIDE normal
        pdf_bytes = self.generar_ride_factura(
            factura,
            detalles,
            opciones,
            storage_path,
            clave_acceso=clave_acceso,
        )

        default_storage.delete(storage_path)
        saved_path = default_storage.save(storage_path, ContentFile(pdf_bytes))
        result_path = saved_path

        if firmar:
            try:
                # Importar el firmador de PDF
                from .pdf_firmador import PDFFirmador

                # Crear instancia del firmador
                firmador = PDFFirmador()

                temp_pdf_path = None
                temp_signed_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                        temp_pdf.write(pdf_bytes)
                        temp_pdf_path = temp_pdf.name

                    temp_signed = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                    temp_signed_path = temp_signed.name
                    temp_signed.close()

                    signed_result_path = firmador.firmar_ride_factura(
                        factura,
                        temp_pdf_path,
                        temp_signed_path,
                    )

                    with open(signed_result_path, 'rb') as signed_file:
                        signed_bytes = signed_file.read()

                    signed_storage_path = f"{target_dir}/{Path(filename).stem}_firmado{Path(filename).suffix}"
                    default_storage.delete(signed_storage_path)
                    saved_signed = default_storage.save(signed_storage_path, ContentFile(signed_bytes))

                    logger.info(f"RIDE firmado exitosamente: {saved_signed}")
                    return saved_path, saved_signed
                finally:
                    if temp_pdf_path and os.path.exists(temp_pdf_path):
                        try:
                            os.unlink(temp_pdf_path)
                        except OSError:
                            pass
                    if temp_signed_path and os.path.exists(temp_signed_path):
                        try:
                            os.unlink(temp_signed_path)
                        except OSError:
                            pass

            except Exception as e:
                logger.warning(f"Error al firmar el RIDE: {e}. Se devolverá solo el PDF sin firmar.")
                return saved_path

        return result_path

    def _obtener_ambiente(self, ambiente):
        """Obtener descripción del ambiente"""
        return "PRODUCCIÓN" if ambiente == "2" else "PRUEBAS"

    def _obtener_tipo_emision(self, tipo_emision):
        """Obtener descripción del tipo de emisión"""
        return "NORMAL" if tipo_emision == "1" else "CONTINGENCIA"
    
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
