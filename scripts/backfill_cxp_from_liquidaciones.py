import os
import sys
from datetime import timedelta
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sistema.settings")

import django

django.setup()

from django.utils import timezone
from inventario.liquidacion_compra.models import LiquidacionCompra
from cxp.models import CuentaPagar


def run() -> None:
    created = 0

    for liq in LiquidacionCompra._unsafe_objects.order_by("id"):
        pagos = list(liq.formas_pago.all())
        pagos_credito = [
            p
            for p in pagos
            if (
                (p.plazo is not None and Decimal(str(p.plazo)) > Decimal("0.00"))
                or str(p.forma_pago) in {"20", "19"}
            )
        ]

        if not pagos_credito:
            continue

        monto = sum((p.total for p in pagos_credito), Decimal("0.00"))
        if monto <= Decimal("0.00"):
            continue

        fecha_base = liq.fecha_emision or timezone.localdate()
        fecha_vencimiento = fecha_base

        for pago in pagos_credito:
            plazo = Decimal(str(pago.plazo or 0))
            if plazo <= Decimal("0.00") and str(pago.forma_pago) in {"20", "19"}:
                plazo = Decimal("30")

            dias = int(plazo)
            unidad = (pago.unidad_tiempo or "dias").strip().lower()
            if unidad.startswith("mes"):
                delta = timedelta(days=dias * 30)
            elif unidad.startswith("anio") or unidad.startswith("año"):
                delta = timedelta(days=dias * 365)
            else:
                delta = timedelta(days=dias)

            candidata = fecha_base + delta
            if candidata > fecha_vencimiento:
                fecha_vencimiento = candidata

        referencia = f"LC {liq.serie_formateada}-{liq.secuencia_formateada}"

        existe = CuentaPagar.objects.filter(
            empresa=liq.empresa,
            proveedor=liq.proveedor,
            referencia_documento=referencia,
        ).exists()
        if existe:
            continue

        CuentaPagar.objects.create(
            empresa=liq.empresa,
            proveedor=liq.proveedor,
            referencia_documento=referencia,
            fecha_emision=fecha_base,
            fecha_vencimiento=fecha_vencimiento,
            monto_total=monto,
            saldo_pendiente=monto,
            estado="PENDIENTE",
            observaciones="Generado automaticamente desde liquidacion de compra (retroactivo).",
        )
        created += 1

    print(f"CXP_CREADAS={created}")
    print(f"CXP_TOTAL={CuentaPagar.objects.count()}")


if __name__ == "__main__":
    run()
