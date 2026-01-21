from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Iterable, Optional


@dataclass(frozen=True)
class DocumentoReporteRow:
    tipo: str
    numero: str
    fecha: date
    identificacion: str
    nombre: str
    total: Optional[Decimal]
    estado: str


def _safe_str(value) -> str:
    return str(value).strip() if value is not None else ""


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _money(value: Optional[Decimal]) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(_to_decimal(value)):.2f}"
    except Exception:
        return "0.00"


_UI_SECUENCIAS_LABELS = {
    "facturas_electronicas": "Facturas Electrónicas",
    "notas_credito_electronicas": "Notas de Crédito Electrónicas",
    "notas_debito_electronicas": "Notas de Débito Electrónicas",
    "liquidaciones_compra_electronicas": "Liquidaciones de Compra Electrónicas",
    "guias_remision_electronicas": "Guías de Remisión Electrónicas",
}


def _labels_for_secuencias(values: list[str]) -> list[str]:
    labels: list[str] = []
    for v in values or []:
        labels.append(_UI_SECUENCIAS_LABELS.get(v, v))
    return labels


def generar_pdf_listado_documentos(
    *,
    empresa_nombre: str,
    empresa_ruc: str,
    empresa_telefonos: str,
    usuario_nombre: str,
    filtros,  # ReporteFacturacionFiltros (reusado)
    filas: Iterable[DocumentoReporteRow],
    now: Optional[datetime] = None,
    resumido: bool = False,
) -> bytes:
    """Genera un PDF con un listado unificado de documentos (Factura/NC/ND/LC/Guía).

    Se usa el mismo formulario de Reportes, pero el dataset y columnas cambian.
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
    small_bold = ParagraphStyle(
        "rep_small_b",
        parent=small,
        fontName="Helvetica-Bold",
    )

    story = []

    story.append(Paragraph(_safe_str(empresa_nombre).upper(), ParagraphStyle("h1", parent=title, fontSize=10)))
    if empresa_ruc:
        story.append(Paragraph(f"RUC: {_safe_str(empresa_ruc)}", small_bold))

    desde = getattr(filtros, "desde", None)
    hasta = getattr(filtros, "hasta", None)
    desde_str = desde.strftime("%d/%m/%Y") if hasattr(desde, "strftime") else ""
    hasta_str = hasta.strftime("%d/%m/%Y") if hasattr(hasta, "strftime") else ""

    story.append(
        Paragraph(
            f"Desde: {desde_str}  Hasta: {hasta_str}  Hora: {now_dt.strftime('%H:%M:%S')}  Usuario: {_safe_str(usuario_nombre)}",
            small,
        )
    )

    sec_sel = _labels_for_secuencias(list(getattr(filtros, "secuencias", []) or []))
    ci_ruc = _safe_str(getattr(filtros, "ci_ruc", ""))

    filtros_line = []
    if sec_sel:
        filtros_line.append(f"Documentos: {', '.join(sec_sel)}")
    if ci_ruc:
        filtros_line.append(f"CI/RUC: {ci_ruc}")

    if filtros_line:
        story.append(Paragraph(" | ".join(filtros_line), small))

    story.append(Spacer(1, 4))

    filas_list = list(filas)

    agrupado_por = _safe_str(getattr(filtros, "agrupado_por", "")).lower()

    if resumido:
        # Resumen por tipo
        resumen: dict[str, dict[str, Decimal | int]] = {}
        for r in filas_list:
            tipo = _safe_str(r.tipo)
            if tipo not in resumen:
                resumen[tipo] = {"count": 0, "total": Decimal("0")}
            resumen[tipo]["count"] = int(resumen[tipo]["count"]) + 1
            if r.total is not None:
                resumen[tipo]["total"] = _to_decimal(resumen[tipo]["total"]) + _to_decimal(r.total)

        story.append(Paragraph("RESUMEN", ParagraphStyle("h2", parent=title, fontSize=9, alignment=0)))
        data = [["Tipo", "Cantidad", "Total"]]
        for tipo in sorted(resumen.keys()):
            data.append([tipo, str(resumen[tipo]["count"]), _money(_to_decimal(resumen[tipo]["total"]))])

        tbl = Table(data, colWidths=[70 * mm, 30 * mm, 35 * mm])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(tbl)
        story.append(Spacer(1, 8))

    story.append(Paragraph("LISTADO DE DOCUMENTOS", ParagraphStyle("h2", parent=title, fontSize=9, alignment=0)))

    header = ["Tipo", "Número", "Fecha", "CI/RUC", "Nombre", "Total", "Estado"]
    rows = [header]

    group_row_indexes: list[int] = []
    current_group = None

    for r in filas_list:
        nombre = _safe_str(r.nombre)
        if agrupado_por == "clientes":
            grp = (nombre or "(Sin nombre)").strip()
            if grp != current_group:
                current_group = grp
                rows.append([f"CLIENTE/PROVEEDOR: {grp}", "", "", "", "", "", ""])
                group_row_indexes.append(len(rows) - 1)

        fecha_str = r.fecha.strftime("%d/%m/%Y") if hasattr(r.fecha, "strftime") else ""
        rows.append(
            [
                _safe_str(r.tipo),
                _safe_str(r.numero),
                fecha_str,
                _safe_str(r.identificacion),
                nombre,
                _money(r.total),
                _safe_str(r.estado),
            ]
        )

    tbl = Table(
        rows,
        colWidths=[22 * mm, 46 * mm, 22 * mm, 30 * mm, 85 * mm, 20 * mm, 30 * mm],
        repeatRows=1,
    )
    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (5, 1), (5, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]

    if group_row_indexes:
        for idx in group_row_indexes:
            table_style.extend(
                [
                    ("SPAN", (0, idx), (-1, idx)),
                    ("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#E2E8F0")),
                    ("TEXTCOLOR", (0, idx), (-1, idx), colors.HexColor("#0F172A")),
                    ("FONTNAME", (0, idx), (-1, idx), "Helvetica-Bold"),
                    ("FONTSIZE", (0, idx), (-1, idx), 8),
                    ("ALIGN", (0, idx), (-1, idx), "LEFT"),
                ]
            )

    tbl.setStyle(TableStyle(table_style))

    story.append(tbl)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
