from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import unicodedata
from typing import Iterable, Optional


WIDTH = 42  # max characters per line for 80mm thermal (monospace)


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _u(value: object) -> str:
    """Uppercase + no accents, safe for None."""
    if value is None:
        return ""
    text = str(value)
    text = _strip_accents(text)
    return text.upper().strip()


def _money(value: object) -> str:
    try:
        if value is None:
            amount = Decimal("0")
        else:
            amount = Decimal(str(value))
    except Exception:
        amount = Decimal("0")
    return f"{amount:.2f}"


def _clip(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[: max(0, max_len - 3)] + "..."


def _center(value: str, width: int = WIDTH) -> str:
    value = value[:width]
    return value.center(width)


def _line(label: str, value: str, width: int = WIDTH, label_width: int = 30) -> str:
    # label left, value right
    label = _u(label)
    value = _u(value)
    if label_width >= width:
        label_width = max(0, width - 1)
    return f"{label:<{label_width}}{value:>{width - label_width}}"[:width]


def _wrap(text: str, width: int) -> list[str]:
    text = _u(text)
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
            continue
        if len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    # hard wrap any overflows (very long tokens)
    out: list[str] = []
    for ln in lines:
        while len(ln) > width:
            out.append(ln[:width])
            ln = ln[width:]
        out.append(ln)
    return out or [""]


@dataclass(frozen=True)
class TicketItem:
    cantidad: int
    descripcion: str
    precio_unitario: Decimal
    descuento: Decimal
    subtotal: Decimal


@dataclass(frozen=True)
class TicketPago:
    forma: str
    valor: Decimal


@dataclass(frozen=True)
class TicketIVA:
    tarifa: Decimal
    valor: Decimal


def render_factura_ticket(
    *,
    # EMISOR
    razon_social: str,
    nombre_comercial: str,
    mensaje_en_facturas: str = "",
    ruc_emisor: str,
    direccion: str,
    ciudad: str,
    telefono: str,
    correo: str,
    regimen: str,
    obligado_contabilidad: str,
    notas: Iterable[str],

    # FACTURA ELECTRONICA
    leyenda: str,
    clave_acceso: str,
    num_autorizacion: str,
    establecimiento: str,
    punto_emision: str,
    secuencial: str,
    fecha: str,
    hora: str,
    usuario: str,
    forma_pago_texto: str,

    # CLIENTE
    cliente_nombre: str,
    cliente_id: str,
    cliente_telf: str,
    cliente_direccion: str,
    cliente_email: str,

    # DETALLE
    items: Iterable[TicketItem],

    # TOTALES
    subtotal: Decimal,
    subtotal_15: Decimal,
    iva_5: Decimal,
    iva_15: Decimal,
    total_a_cancelar: Decimal,

    # PAGO
    su_pago: Decimal,
    su_cambio: Decimal,

    # PIE
    url_consulta: str,
) -> str:
    def star_line() -> str:
        return "*" * WIDTH

    def dash_line() -> str:
        return "-" * WIDTH

    def kv(label: str, value: object, label_width: int = 30) -> str:
        return _line(label, _money(value) if isinstance(value, Decimal) else _u(value), label_width=label_width)

    def emit_line(text: str) -> None:
        lines.append(_u(text)[:WIDTH])

    def emit_wrapped(prefix: str, text: str) -> None:
        for ln in _wrap(f"{prefix}{text}", WIDTH):
            lines.append(ln[:WIDTH])

    lines: list[str] = []

    # Encabezado emisor
    titulo = nombre_comercial or razon_social
    if titulo:
        emit_line(f"*** {titulo} ***")
    if mensaje_en_facturas:
        for ln in _wrap(mensaje_en_facturas, WIDTH):
            lines.append(_center(ln[:WIDTH], WIDTH))
    if ruc_emisor:
        emit_line(f"RUC: {ruc_emisor}")
    if direccion:
        emit_wrapped("DIRECCION: ", direccion)
    if ciudad:
        emit_line(f"{ciudad} - ECUADOR")
    else:
        emit_line("ECUADOR")
    if telefono:
        emit_line(f"TELEFONO: {telefono}")
    if correo:
        emit_wrapped("CORREO: ", correo)
    if regimen:
        emit_line(f"CONTRIBUYENTE {regimen}")

    # Notas
    notas_list = [n for n in (notas or []) if _u(n)]
    if notas_list:
        lines.append("")
        emit_line("***** NOTA *****")
        for n in notas_list:
            for ln in _wrap(n, WIDTH - 1):
                lines.append(("-" + ln)[:WIDTH])
        lines.append("")

    emit_line(f"OBLIGADO A LLEVAR CONTABILIDAD: {obligado_contabilidad}")

    # Bloque factura electrónica
    lines.append(star_line())
    emit_line("F A C T U R A  E L E C T R O N I C A".center(WIDTH))
    if leyenda:
        emit_line(f"*** {leyenda} ***")

    ca = _u(clave_acceso)
    if ca:
        ca_line = f"CA/AUTORIZACION: {ca}"
        if len(_u(ca_line)) <= WIDTH:
            emit_line(ca_line)
        else:
            emit_line("CA/AUTORIZACION:")
            for i in range(0, len(ca), WIDTH):
                lines.append(ca[i : i + WIDTH])

    if num_autorizacion:
        emit_wrapped("", num_autorizacion)

    lines.append(star_line())

    # Número, fecha/hora, usuario
    numero = f"{establecimiento}-{punto_emision}-{secuencial}"
    if forma_pago_texto:
        emit_line(f"{numero} ({forma_pago_texto})")
    else:
        emit_line(numero)
    emit_line(f"FECHA: {fecha}  {hora}")
    if usuario:
        emit_wrapped("USUARIO: ", usuario)

    lines.append("")

    # Cliente
    emit_wrapped("CLIENTE: ", cliente_nombre)
    if cliente_id or cliente_telf:
        emit_line(f"RUC/CI: {cliente_id}   TELF: {cliente_telf}".strip())
    if cliente_direccion:
        emit_wrapped("DIRECCION: ", cliente_direccion)
    if cliente_email:
        emit_wrapped("E-MAIL: ", cliente_email)

    lines.append("")

    # Detalle
    items_list = list(items or [])
    left = f"DETALLE ({len(items_list)} ITEMS)"
    right = "VALOR"
    if len(left) + len(right) + 1 <= WIDTH:
        lines.append((left + " " * (WIDTH - len(left) - len(right)) + right)[:WIDTH])
    else:
        lines.append(_clip(left, WIDTH))
    lines.append(dash_line())

    # Formato de items: 3 qty +1 +20 desc +1 +8 punit +1 +8 total = 42
    for it in items_list:
        qty = str(int(it.cantidad)) if it.cantidad is not None else "0"
        qty = qty[-3:]
        desc_lines = _wrap(it.descripcion, 20)
        punit = _money(it.precio_unitario)
        totl = _money(it.subtotal)
        first = desc_lines[0] if desc_lines else ""
        lines.append(f"{qty:>3} {first:<20} {punit:>8} {totl:>8}"[:WIDTH])
        for extra in desc_lines[1:]:
            lines.append(f"{'':>3} {extra:<20} {'':>8} {'':>8}"[:WIDTH])

    lines.append(dash_line())

    # Totales
    lines.append(kv("SUBTOTAL", subtotal))
    if Decimal(str(subtotal_15 or 0)) != Decimal('0'):
        lines.append(kv("SUBTOTAL 15%", subtotal_15))
    if Decimal(str(iva_5 or 0)) != Decimal('0'):
        lines.append(kv("IVA 5%", iva_5))
    if Decimal(str(iva_15 or 0)) != Decimal('0'):
        lines.append(kv("IVA 15%", iva_15))
    lines.append(kv("TOTAL A CANCELAR", total_a_cancelar))

    lines.append("")

    lines.append(kv("SU PAGO", su_pago))
    lines.append(kv("SU CAMBIO", su_cambio))

    # Pie
    lines.append("")
    lines.append(star_line())
    # Sitio web (sin el texto de "FACTURA ELECTRONICA")
    emit_line("www.catalinasoft-ec.com")
    lines.append(star_line())

    lines.append("")
    # Espacio y línea para firma del cliente
    lines.append("")
    lines.append("")
    lines.append(("_" * WIDTH)[:WIDTH])
    lines.append("FIRMA CLIENTE"[:WIDTH])

    final_lines = [ln[:WIDTH] for ln in lines]
    return "\n".join(final_lines).rstrip() + "\n"
