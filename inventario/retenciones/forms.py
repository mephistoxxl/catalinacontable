from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.core.exceptions import ValidationError
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

    @staticmethod
    def _contar_dias_habiles(fecha_inicio, fecha_fin) -> int:
        if not fecha_inicio or not fecha_fin or fecha_fin <= fecha_inicio:
            return 0

        dias = 0
        cursor = fecha_inicio
        while cursor < fecha_fin:
            cursor = cursor + timedelta(days=1)
            if cursor.weekday() < 5:
                dias += 1
        return dias

    def clean_identificacion_sujeto(self):
        identificacion = (self.cleaned_data.get("identificacion_sujeto") or "").strip()
        if not identificacion:
            raise ValidationError("La identificación del proveedor es obligatoria.")
        if not identificacion.isdigit() or len(identificacion) != 13 or not identificacion.endswith('001'):
            raise ValidationError("El RUC del proveedor debe tener 13 dígitos y terminar en 001.")
        return identificacion

    def clean_autorizacion_doc_sustento(self):
        autorizacion = (self.cleaned_data.get("autorizacion_doc_sustento") or "").strip()
        if not autorizacion:
            raise ValidationError("La autorización del documento de sustento es obligatoria.")
        if not autorizacion.isdigit() or len(autorizacion) != 49:
            raise ValidationError("La autorización del documento de sustento debe tener exactamente 49 dígitos.")
        return autorizacion

    def clean(self):
        cleaned_data = super().clean()
        fecha_doc = cleaned_data.get("fecha_emision")
        fecha_ret = cleaned_data.get("fecha_emision_retencion")

        if fecha_doc and fecha_ret:
            if fecha_ret < fecha_doc:
                self.add_error("fecha_emision_retencion", "La fecha de retención no puede ser anterior a la fecha del documento de sustento.")
            else:
                dias_habiles = self._contar_dias_habiles(fecha_doc, fecha_ret)
                if dias_habiles > 5:
                    self.add_error(
                        "fecha_emision_retencion",
                        "La retención excede los 5 días hábiles permitidos desde la emisión del documento de sustento.",
                    )

        return cleaned_data
