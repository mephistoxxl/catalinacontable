from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Iterable, Optional


@dataclass(frozen=True)
class ReporteFacturacionFiltros:
    desde: date
    hasta: date
    ordenado_por: str  # secuencia|fecha|cliente
    agrupado_por: str  # ninguno|clientes
    ci_ruc: str
    informe_resumido: bool
    exportar_excel: bool
    almacenes: list[str]
    secuencias: list[str]
    formas_pago: list[str]
    facturadores: list[str]


def _money(value) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except Exception:
        return "0.00"


def _safe_str(value) -> str:
    return str(value).strip() if value is not None else ""


def _build_filters_line(f: ReporteFacturacionFiltros) -> str:
    partes: list[str] = []

    if f.almacenes:
        partes.append(f"Almacenes: {', '.join(f.almacenes)}")
    if f.secuencias:
        partes.append(f"Secuencias: {', '.join(f.secuencias)}")
    if f.formas_pago:
        partes.append(f"Forma de pago: {', '.join(f.formas_pago)}")
    if f.facturadores:
        partes.append(f"Facturadores: {', '.join(f.facturadores)}")
    if f.ci_ruc:
        partes.append(f"Cliente: {f.ci_ruc}")

    partes.append(f"Ordenado por: {f.ordenado_por}")
    partes.append(f"Agrupado por: {f.agrupado_por}")

    return " | ".join(partes)


def generar_pdf_listado_facturacion(
    *,
    empresa_nombre: str,
    empresa_ruc: str,
    empresa_telefonos: str,
    usuario_nombre: str,
    filtros: ReporteFacturacionFiltros,
    facturas: Iterable,
    now: Optional[datetime] = None,
) -> bytes:
    """Genera el PDF del 'Listado de Facturacion General' (tipo tabla) similar al formato mostrado.

    - `facturas` debe ser iterable de objetos Factura con:
      establecimiento_formatted, punto_emision_formatted, secuencia_formatted,
      identificacion_cliente, nombre_cliente, fecha_emision, propina,
      sub_monto, total_descuento, monto_general, y relación `totales_impuestos`.
    """

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    now_dt = now or datetime.now()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "rep_title",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=12,
        alignment=1,  # center
        spaceAfter=4,
    )
    small = ParagraphStyle(
        "rep_small",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=9,
        spaceAfter=2,
    )
    small_bold = ParagraphStyle(
        "rep_small_b",
        parent=small,
        fontName="Helvetica-Bold",
    )

    story = []

    # Cabecera (similar a la imagen)
    story.append(Paragraph(_safe_str(empresa_nombre).upper(), ParagraphStyle("h1", parent=title, fontSize=10)))
    if empresa_ruc:
        story.append(Paragraph(f"<b>RUC</b> {empresa_ruc}", small))
    if empresa_telefonos:
        story.append(Paragraph(f"<b>TELEFONOS:</b> {empresa_telefonos}", small))
    story.append(Paragraph("<b>Listado de Facturacion General</b>", title))

    story.append(
        Paragraph(
            f"<b>Desde:</b> {filtros.desde.strftime('%d/%m/%Y')} &nbsp;&nbsp;"
            f"<b>Hasta:</b> {filtros.hasta.strftime('%d/%m/%Y')} &nbsp;&nbsp;"
            f"<b>Hora:</b> {now_dt.strftime('%H:%M:%S')} &nbsp;&nbsp;"
            f"<b>Usuario:</b> {usuario_nombre}",
            small,
        )
    )

    filtros_linea = _build_filters_line(filtros)
    if filtros_linea:
        story.append(Paragraph(f"<b>REPORTE FILTRADO POR:</b> {filtros_linea}", small))

    story.append(Spacer(1, 6))

    # Tabla
    header = [
        "Secuencias",
        "Facturas Electrónicas",
        "CI/RUC",
        "Cliente",
        "FP",
        "Emisión",
        "SubTotal",
        "Descuento",
        "SUB.IVA 0%",
        "SUB.IVA 12%",
        "IVA",
        "Propina",
        "TOTAL",
    ]

    rows = [header]

    total_sub = Decimal("0")
    total_desc = Decimal("0")
    total_sub0 = Decimal("0")
    total_sub12 = Decimal("0")
    total_iva = Decimal("0")
    total_propina = Decimal("0")
    total_total = Decimal("0")

    for fac in facturas:
        # Forma de pago (primera) o 'VARIOS'
        fp_label = ""
        try:
            fps = list(getattr(fac, "formas_pago").all())
            if len(fps) == 1:
                fp_label = fps[0].get_forma_pago_display() if hasattr(fps[0], "get_forma_pago_display") else _safe_str(getattr(fps[0], "forma_pago", ""))
            elif len(fps) > 1:
                fp_label = "Varios"
        except Exception:
            fp_label = ""

        sec = f"{getattr(fac, 'establecimiento_formatted', '')} {getattr(fac, 'punto_emision_formatted', '')}".strip()
        num = _safe_str(getattr(fac, "secuencia_formatted", ""))

        sub = Decimal(str(getattr(fac, "sub_monto", 0) or 0))
        desc = Decimal(str(getattr(fac, "total_descuento", 0) or 0))
        prop = Decimal(str(getattr(fac, "propina", 0) or 0))
        tot = Decimal(str(getattr(fac, "monto_general", 0) or 0))

        # Subtotales IVA por propiedades (si existen) o por totales_impuestos
        sub0 = Decimal("0")
        sub12 = Decimal("0")
        iva_val = Decimal("0")
        try:
            sub0 = Decimal(str(getattr(fac, "subtotal_0", 0) or 0))
            sub12 = Decimal(str(getattr(fac, "subtotal_12", 0) or 0))
            iva_val = Decimal(str(getattr(fac, "iva_12", 0) or 0))
        except Exception:
            pass

        if iva_val == 0:
            try:
                for ti in getattr(fac, "totales_impuestos").all():
                    if getattr(ti, "codigo", "") == "2":
                        iva_val += Decimal(str(getattr(ti, "valor", 0) or 0))
            except Exception:
                pass

        total_sub += sub
        total_desc += desc
        total_sub0 += sub0
        total_sub12 += sub12
        total_iva += iva_val
        total_propina += prop
        total_total += tot

        fecha_em = getattr(fac, "fecha_emision", None)
        if hasattr(fecha_em, "strftime"):
            fecha_str = fecha_em.strftime("%d/%m/%Y")
        else:
            fecha_str = ""

        rows.append(
            [
                sec,
                num,
                _safe_str(getattr(fac, "identificacion_cliente", "")),
                _safe_str(getattr(fac, "nombre_cliente", ""))[:45],
                fp_label,
                fecha_str,
                _money(sub),
                _money(desc),
                _money(sub0),
                _money(sub12),
                _money(iva_val),
                _money(prop),
                _money(tot),
            ]
        )

    # Totales
    rows.append(
        [
            "",
            "",
            "",
            "TOTAL",
            "",
            "",
            _money(total_sub),
            _money(total_desc),
            _money(total_sub0),
            _money(total_sub12),
            _money(total_iva),
            _money(total_propina),
            _money(total_total),
        ]
    )

    # Ajuste de anchos para A4 landscape
    col_widths = [
        22 * mm,  # Secuencias
        22 * mm,  # Facturas Electrónicas
        28 * mm,  # CI/RUC
        55 * mm,  # Cliente
        12 * mm,  # FP
        20 * mm,  # Emisión
        18 * mm,  # SubTotal
        18 * mm,  # Descuento
        20 * mm,  # SUB 0
        20 * mm,  # SUB 12
        16 * mm,  # IVA
        16 * mm,  # Propina
        18 * mm,  # TOTAL
    ]

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7),
                ("FONT", (0, 1), (-1, -2), "Helvetica", 7),
                ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (4, -1), "LEFT"),
                ("ALIGN", (5, 1), (5, -1), "CENTER"),
                ("ALIGN", (6, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
