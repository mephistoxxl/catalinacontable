from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import random


IVA_RETENCION_PORCENTAJE_POR_CODIGO = {
    "721": Decimal("10.00"),
    "723": Decimal("20.00"),
    "725": Decimal("30.00"),
    "729": Decimal("70.00"),
    "731": Decimal("100.00"),
    "7": Decimal("70.00"),
}

RENTA_PORCENTAJE_SUGERIDO = {
    "312": Decimal("1.75"),
    "332": Decimal("2.75"),
    "304": Decimal("2.00"),
    "308": Decimal("2.00"),
    "343": Decimal("8.00"),
    "320": Decimal("2.00"),
    "322": Decimal("2.00"),
    "344": Decimal("3.00"),
    "3440": Decimal("10.00"),
    "303": Decimal("10.00"),
    "307": Decimal("10.00"),
    "304B": Decimal("10.00"),
    "346": Decimal("1.00"),
    "350": Decimal("1.00"),
    "3481": Decimal("1.00"),
}

TIPO_IDENTIFICACION_POR_LONGITUD = {
    10: "05",  # Cédula
    13: "04",  # RUC
}

CODIGO_PORCENTAJE_IVA_SUSTENTO = {
    Decimal("0.00"): "0",
    Decimal("5.00"): "5",
    Decimal("8.00"): "8",
    Decimal("12.00"): "2",
    Decimal("13.00"): "10",
    Decimal("15.00"): "4",
}


@dataclass
class TotalesRetencion:
    renta: Decimal
    iva: Decimal
    total: Decimal


def _money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_decimal(value: Decimal, places: int = 2) -> str:
    quant = Decimal("1").scaleb(-places)
    return f"{Decimal(value).quantize(quant, rounding=ROUND_HALF_UP):.{places}f}"


def porcentaje_iva_por_codigo(codigo_iva: str) -> Decimal:
    return IVA_RETENCION_PORCENTAJE_POR_CODIGO.get((codigo_iva or "").strip(), Decimal("0.00"))


def porcentaje_renta_sugerido(codigo_renta: str) -> Decimal:
    return RENTA_PORCENTAJE_SUGERIDO.get((codigo_renta or "").strip().upper(), Decimal("0.00"))


def calcular_valor_retenido(base: Decimal, porcentaje: Decimal) -> Decimal:
    return _money(base * porcentaje / Decimal("100"))


def inferir_tipo_identificacion(identificacion: str) -> str:
    numero = "".join(ch for ch in (identificacion or "") if ch.isdigit())
    if len(numero) in TIPO_IDENTIFICACION_POR_LONGITUD:
        return TIPO_IDENTIFICACION_POR_LONGITUD[len(numero)]
    if numero:
        return "04" if len(numero) >= 13 else "05"
    return "05"


def obtener_codigo_porcentaje_iva_sustento(porcentaje_iva: Decimal) -> str:
    clave = Decimal(porcentaje_iva or 0).quantize(Decimal("0.00"))
    return CODIGO_PORCENTAJE_IVA_SUSTENTO.get(clave, "0")


def calcular_modulo11(cadena_48: str) -> str:
    pesos = [2, 3, 4, 5, 6, 7]
    total = 0
    i = 0
    for d in reversed(cadena_48):
        total += int(d) * pesos[i]
        i = (i + 1) % len(pesos)

    residuo = total % 11
    digito = 11 - residuo
    if digito == 11:
        digito = 0
    elif digito == 10:
        digito = 1
    return str(digito)


def generar_clave_acceso_retencion(
    *,
    fecha_emision: date,
    ruc_emisor: str,
    ambiente: str,
    establecimiento: str,
    punto_emision: str,
    secuencial: str,
    tipo_emision: str = "1",
    codigo_numerico: str | None = None,
) -> str:
    fecha_str = fecha_emision.strftime("%d%m%Y")
    tipo_comprobante = "07"
    codigo = codigo_numerico or f"{random.randint(0, 99999999):08d}"

    base = (
        f"{fecha_str}"
        f"{tipo_comprobante}"
        f"{ruc_emisor}"
        f"{ambiente}"
        f"{establecimiento}{punto_emision}"
        f"{secuencial}"
        f"{codigo}"
        f"{tipo_emision}"
    )
    dv = calcular_modulo11(base)
    return f"{base}{dv}"


def calcular_totales_desde_componentes(
    *,
    base_iva_0: Decimal,
    base_iva_5: Decimal,
    base_no_obj_iva: Decimal,
    base_exento_iva: Decimal,
    base_iva: Decimal,
    monto_iva: Decimal,
    monto_ice: Decimal,
) -> tuple[Decimal, Decimal]:
    total_sin_impuestos = _money(base_iva_0 + base_iva_5 + base_no_obj_iva + base_exento_iva + base_iva)
    importe_total = _money(total_sin_impuestos + monto_iva + monto_ice)
    return total_sin_impuestos, importe_total


def format_decimal_for_xml(value: Decimal, places: int = 2) -> str:
    return _format_decimal(value, places)
