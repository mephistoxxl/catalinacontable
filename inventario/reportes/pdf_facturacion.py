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

    def _fp_label_for(fac) -> str:
        try:
            fps = list(getattr(fac, "formas_pago").all())
            if len(fps) == 1:
                return fps[0].get_forma_pago_display() if hasattr(fps[0], "get_forma_pago_display") else _safe_str(getattr(fps[0], "forma_pago", ""))
            if len(fps) > 1:
                return "Varios"
        except Exception:
            return ""
        return ""

    def _extract_vals(fac):
        sec = f"{getattr(fac, 'establecimiento_formatted', '')} {getattr(fac, 'punto_emision_formatted', '')}".strip()
        num = _safe_str(getattr(fac, "secuencia_formatted", ""))
        ci = _safe_str(getattr(fac, "identificacion_cliente", ""))
        nombre = _safe_str(getattr(fac, "nombre_cliente", ""))[:45]

        sub = Decimal(str(getattr(fac, "sub_monto", 0) or 0))
        desc = Decimal(str(getattr(fac, "total_descuento", 0) or 0))
        prop = Decimal(str(getattr(fac, "propina", 0) or 0))
        tot = Decimal(str(getattr(fac, "monto_general", 0) or 0))

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

        fecha_em = getattr(fac, "fecha_emision", None)
        fecha_str = fecha_em.strftime("%d/%m/%Y") if hasattr(fecha_em, "strftime") else ""
        return sec, num, ci, nombre, _fp_label_for(fac), fecha_str, sub, desc, sub0, sub12, iva_val, prop, tot

    # Totales generales
    total_sub = Decimal("0")
    total_desc = Decimal("0")
    total_sub0 = Decimal("0")
    total_sub12 = Decimal("0")
    total_iva = Decimal("0")
    total_propina = Decimal("0")
    total_total = Decimal("0")

    # Estilos especiales por fila
    group_header_rows: list[int] = []
    group_subtotal_rows: list[int] = []

    # Materializar iterable (QuerySet/iterable) porque para agrupar necesitamos lookahead
    facturas_list = list(facturas)

    agrupar_clientes = (filtros.agrupado_por or "").strip().lower() == "clientes"

    if not agrupar_clientes:
        for fac in facturas_list:
            sec, num, ci, nombre, fp_label, fecha_str, sub, desc, sub0, sub12, iva_val, prop, tot = _extract_vals(fac)

            total_sub += sub
            total_desc += desc
            total_sub0 += sub0
            total_sub12 += sub12
            total_iva += iva_val
            total_propina += prop
            total_total += tot

            rows.append(
                [
                    sec,
                    num,
                    ci,
                    nombre,
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
    else:
        current_key = None
        # Totales por cliente
        c_sub = Decimal("0")
        c_desc = Decimal("0")
        c_sub0 = Decimal("0")
        c_sub12 = Decimal("0")
        c_iva = Decimal("0")
        c_prop = Decimal("0")
        c_tot = Decimal("0")
        current_label = ""

        def _flush_client_subtotal():
            nonlocal c_sub, c_desc, c_sub0, c_sub12, c_iva, c_prop, c_tot
            if current_key is None:
                return
            rows.append(
                [
                    "SUBTOTAL CLIENTE",
                    "",
                    "",
                    "",
                    "",
                    "",
                    _money(c_sub),
                    _money(c_desc),
                    _money(c_sub0),
                    _money(c_sub12),
                    _money(c_iva),
                    _money(c_prop),
                    _money(c_tot),
                ]
            )
            group_subtotal_rows.append(len(rows) - 1)
            c_sub = c_desc = c_sub0 = c_sub12 = c_iva = c_prop = c_tot = Decimal("0")

        for fac in facturas_list:
            sec, num, ci, nombre, fp_label, fecha_str, sub, desc, sub0, sub12, iva_val, prop, tot = _extract_vals(fac)
            key = (ci, nombre)

            if current_key is None:
                current_key = key
                current_label = f"CLIENTE: {nombre} ({ci})".strip()
                rows.append([current_label] + [""] * (len(header) - 1))
                group_header_rows.append(len(rows) - 1)
            elif key != current_key:
                _flush_client_subtotal()
                current_key = key
                current_label = f"CLIENTE: {nombre} ({ci})".strip()
                rows.append([current_label] + [""] * (len(header) - 1))
                group_header_rows.append(len(rows) - 1)

            # Acumular totales
            total_sub += sub
            total_desc += desc
            total_sub0 += sub0
            total_sub12 += sub12
            total_iva += iva_val
            total_propina += prop
            total_total += tot

            c_sub += sub
            c_desc += desc
            c_sub0 += sub0
            c_sub12 += sub12
            c_iva += iva_val
            c_prop += prop
            c_tot += tot

            # Filas de factura dentro del grupo (sin repetir CI/RUC y Cliente)
            rows.append(
                [
                    sec,
                    num,
                    "",
                    "",
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

        _flush_client_subtotal()

    # Total general
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
    base_style = [
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

    # Estilos de agrupación (encabezado de cliente + subtotal cliente)
    for r in group_header_rows:
        base_style.extend(
            [
                ("SPAN", (0, r), (-1, r)),
                ("FONT", (0, r), (-1, r), "Helvetica-Bold", 7),
                ("BACKGROUND", (0, r), (-1, r), colors.lightgrey),
                ("ALIGN", (0, r), (-1, r), "LEFT"),
            ]
        )
    for r in group_subtotal_rows:
        base_style.extend(
            [
                ("SPAN", (0, r), (5, r)),
                ("FONT", (0, r), (-1, r), "Helvetica-Bold", 7),
                ("BACKGROUND", (0, r), (-1, r), colors.whitesmoke),
                ("ALIGN", (0, r), (5, r), "LEFT"),
            ]
        )

    table.setStyle(
        TableStyle(
            base_style
        )
    )

    story.append(table)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def generar_pdf_resumen_facturacion(
    *,
    empresa_nombre: str,
    empresa_ruc: str,
    empresa_telefonos: str,
    usuario_nombre: str,
    filtros: ReporteFacturacionFiltros,
    facturas: Iterable,
    now: Optional[datetime] = None,
) -> bytes:
    """Genera un PDF resumido (agregado por cliente) para el reporte de facturación."""

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    now_dt = now or datetime.now()

    def _to_decimal(value) -> Decimal:
        try:
            return Decimal(str(value or 0))
        except Exception:
            return Decimal("0")

    def _extract_tax_vals(fac):
        sub = _to_decimal(getattr(fac, "sub_monto", 0))
        desc = _to_decimal(getattr(fac, "total_descuento", 0))
        prop = _to_decimal(getattr(fac, "propina", 0))
        tot = _to_decimal(getattr(fac, "monto_general", 0))

        sub0 = Decimal("0")
        sub12 = Decimal("0")
        iva_val = Decimal("0")
        try:
            sub0 = _to_decimal(getattr(fac, "subtotal_0", 0))
            sub12 = _to_decimal(getattr(fac, "subtotal_12", 0))
            iva_val = _to_decimal(getattr(fac, "iva_12", 0))
        except Exception:
            pass

        if iva_val == 0:
            try:
                for ti in getattr(fac, "totales_impuestos").all():
                    if getattr(ti, "codigo", "") == "2":
                        iva_val += _to_decimal(getattr(ti, "valor", 0))
            except Exception:
                pass

        return sub, desc, sub0, sub12, iva_val, prop, tot

    # Agrupar por cliente (CI/RUC + nombre)
    grupos: dict[tuple[str, str], dict[str, Decimal | int]] = {}
    for fac in list(facturas):
        ci = _safe_str(getattr(fac, "identificacion_cliente", ""))
        nombre = _safe_str(getattr(fac, "nombre_cliente", ""))
        key = (ci, nombre)
        if key not in grupos:
            grupos[key] = {
                "count": 0,
                "sub": Decimal("0"),
                "desc": Decimal("0"),
                "sub0": Decimal("0"),
                "sub12": Decimal("0"),
                "iva": Decimal("0"),
                "prop": Decimal("0"),
                "tot": Decimal("0"),
            }

        sub, desc, sub0, sub12, iva_val, prop, tot = _extract_tax_vals(fac)
        grupos[key]["count"] = int(grupos[key]["count"]) + 1
        grupos[key]["sub"] = _to_decimal(grupos[key]["sub"]) + sub
        grupos[key]["desc"] = _to_decimal(grupos[key]["desc"]) + desc
        grupos[key]["sub0"] = _to_decimal(grupos[key]["sub0"]) + sub0
        grupos[key]["sub12"] = _to_decimal(grupos[key]["sub12"]) + sub12
        grupos[key]["iva"] = _to_decimal(grupos[key]["iva"]) + iva_val
        grupos[key]["prop"] = _to_decimal(grupos[key]["prop"]) + prop
        grupos[key]["tot"] = _to_decimal(grupos[key]["tot"]) + tot

    # Orden
    grupos_items = sorted(grupos.items(), key=lambda it: (it[0][1], it[0][0]))

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
        alignment=1,
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

    story = []
    story.append(Paragraph(_safe_str(empresa_nombre).upper(), ParagraphStyle("h1", parent=title, fontSize=10)))
    if empresa_ruc:
        story.append(Paragraph(f"<b>RUC</b> {empresa_ruc}", small))
    if empresa_telefonos:
        story.append(Paragraph(f"<b>TELEFONOS:</b> {empresa_telefonos}", small))
    story.append(Paragraph("<b>Listado de Facturacion General (Resumido)</b>", title))
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

    header = [
        "CI/RUC",
        "Cliente",
        "#Docs",
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
    total_prop = Decimal("0")
    total_tot = Decimal("0")

    for (ci, nombre), agg in grupos_items:
        count = int(agg["count"])  # type: ignore[arg-type]
        sub = _to_decimal(agg["sub"])
        desc = _to_decimal(agg["desc"])
        sub0 = _to_decimal(agg["sub0"])
        sub12 = _to_decimal(agg["sub12"])
        iva = _to_decimal(agg["iva"])
        prop = _to_decimal(agg["prop"])
        tot = _to_decimal(agg["tot"])

        total_sub += sub
        total_desc += desc
        total_sub0 += sub0
        total_sub12 += sub12
        total_iva += iva
        total_prop += prop
        total_tot += tot

        rows.append(
            [
                ci,
                nombre[:55],
                str(count),
                _money(sub),
                _money(desc),
                _money(sub0),
                _money(sub12),
                _money(iva),
                _money(prop),
                _money(tot),
            ]
        )

    rows.append(
        [
            "",
            "TOTAL",
            "",
            _money(total_sub),
            _money(total_desc),
            _money(total_sub0),
            _money(total_sub12),
            _money(total_iva),
            _money(total_prop),
            _money(total_tot),
        ]
    )

    col_widths = [
        30 * mm,
        85 * mm,
        15 * mm,
        22 * mm,
        22 * mm,
        22 * mm,
        22 * mm,
        18 * mm,
        18 * mm,
        22 * mm,
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
                ("ALIGN", (0, 1), (1, -1), "LEFT"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
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
