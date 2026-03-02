from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.utils import timezone

from .models import ComprobanteRetencion


class ComprobanteRetencionForm(forms.ModelForm):
    renta_base = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=20, initial=Decimal("0.00"))
    renta_porcentaje = forms.DecimalField(required=False, min_value=0, decimal_places=4, max_digits=7, initial=Decimal("0.00"))
    codigo_renta = forms.CharField(required=False, max_length=10, initial="304B")

    iva_base = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=20, initial=Decimal("0.00"))
    iva_porcentaje = forms.DecimalField(required=False, min_value=0, decimal_places=4, max_digits=7, initial=Decimal("0.00"))
    codigo_iva = forms.CharField(required=False, max_length=10, initial="721")

    class Meta:
        model = ComprobanteRetencion
        fields = [
            "fecha_emision",
            "identificacion_sujeto",
            "razon_social_sujeto",
            "tipo_documento_sustento",
            "establecimiento_doc",
            "punto_emision_doc",
            "secuencia_doc",
            "autorizacion_doc_sustento",
            "forma_pago_sri",
            "sustento_tributario",
            "forma_pago",
            "base_iva_0",
            "base_iva_5",
            "base_no_obj_iva",
            "base_exento_iva",
            "base_iva",
            "monto_iva",
            "porcentaje_iva",
            "monto_ice",
            "tipo_retencion",
            "fecha_emision_retencion",
            "establecimiento_retencion",
            "punto_emision_retencion",
            "secuencia_retencion",
            "autorizacion_retencion",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoy = timezone.localdate()
        self.fields["fecha_emision"].initial = self.initial.get("fecha_emision", hoy)
        self.fields["fecha_emision_retencion"].initial = self.initial.get("fecha_emision_retencion", hoy)

    @staticmethod
    def _valor_monetario(valor: Decimal | None) -> Decimal:
        return (valor or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def valor_renta_retenido(self) -> Decimal:
        base = self.cleaned_data.get("renta_base") or Decimal("0.00")
        porcentaje = self.cleaned_data.get("renta_porcentaje") or Decimal("0.00")
        return self._valor_monetario(base * porcentaje / Decimal("100"))

    def valor_iva_retenido(self) -> Decimal:
        base = self.cleaned_data.get("iva_base") or Decimal("0.00")
        porcentaje = self.cleaned_data.get("iva_porcentaje") or Decimal("0.00")
        return self._valor_monetario(base * porcentaje / Decimal("100"))
