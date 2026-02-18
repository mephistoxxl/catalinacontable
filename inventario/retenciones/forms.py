from __future__ import annotations

from decimal import Decimal

from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..models import Proveedor
from .models import (
    CODIGO_IMPUESTO_CHOICES,
    COD_DOC_SUSTENTO_CHOICES,
    TIPO_IDENTIFICACION_SUJETO_CHOICES,
    RetencionCampoAdicional,
    RetencionCompra,
    RetencionImpuesto,
)


class RetencionCompraForm(forms.ModelForm):
    secuencia_config_id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = RetencionCompra
        fields = [
            "proveedor",
            "fecha_emision",
            "fecha_emision_doc_sustento",
            "establecimiento",
            "punto_emision",
            "secuencia",
            "version_xml",
            "cod_doc_sustento",
            "num_doc_sustento",
            "num_aut_doc_sustento",
            "tipo_identificacion_sujeto_retenido",
            "razon_social_sujeto_retenido",
            "identificacion_sujeto_retenido",
            "periodo_fiscal",
            "total_sin_impuestos_doc",
            "total_iva_doc",
            "importe_total_doc",
            "observaciones",
        ]
        widgets = {
            "proveedor": forms.Select(attrs={"class": "form-control"}),
            "fecha_emision": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "fecha_emision_doc_sustento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "establecimiento": forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"}),
            "punto_emision": forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"}),
            "secuencia": forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"}),
            "version_xml": forms.Select(attrs={"class": "form-control"}),
            "cod_doc_sustento": forms.Select(attrs={"class": "form-control"}),
            "num_doc_sustento": forms.TextInput(attrs={"class": "form-control"}),
            "num_aut_doc_sustento": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_identificacion_sujeto_retenido": forms.Select(attrs={"class": "form-control"}),
            "razon_social_sujeto_retenido": forms.TextInput(attrs={"class": "form-control"}),
            "identificacion_sujeto_retenido": forms.TextInput(attrs={"class": "form-control"}),
            "periodo_fiscal": forms.TextInput(attrs={"class": "form-control", "placeholder": "MM/AAAA"}),
            "total_sin_impuestos_doc": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "total_iva_doc": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "importe_total_doc": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, empresa=None, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)

        if empresa:
            self.fields["proveedor"].queryset = Proveedor.objects.filter(empresa=empresa).order_by("razon_social_proveedor")
        else:
            self.fields["proveedor"].queryset = Proveedor.objects.none()

        self.fields["tipo_identificacion_sujeto_retenido"].choices = TIPO_IDENTIFICACION_SUJETO_CHOICES
        self.fields["cod_doc_sustento"].choices = COD_DOC_SUSTENTO_CHOICES

        if not self.initial.get("fecha_emision"):
            self.initial["fecha_emision"] = timezone.localdate()
        if not self.initial.get("fecha_emision_doc_sustento"):
            self.initial["fecha_emision_doc_sustento"] = timezone.localdate()

        proveedor_id = self.data.get("proveedor") or self.initial.get("proveedor")
        if proveedor_id:
            try:
                proveedor = self.fields["proveedor"].queryset.get(pk=proveedor_id)
                self.initial.setdefault("tipo_identificacion_sujeto_retenido", proveedor.tipoIdentificacion)
                self.initial.setdefault("identificacion_sujeto_retenido", proveedor.identificacion_proveedor)
                self.initial.setdefault("razon_social_sujeto_retenido", proveedor.razon_social_proveedor)
            except (Proveedor.DoesNotExist, ValueError, TypeError):
                pass

    def clean(self):
        cleaned = super().clean()
        proveedor = cleaned.get("proveedor")

        if proveedor:
            cleaned["tipo_identificacion_sujeto_retenido"] = proveedor.tipoIdentificacion
            cleaned["identificacion_sujeto_retenido"] = proveedor.identificacion_proveedor
            cleaned["razon_social_sujeto_retenido"] = proveedor.razon_social_proveedor

        total_sin = Decimal(cleaned.get("total_sin_impuestos_doc") or 0)
        total_iva = Decimal(cleaned.get("total_iva_doc") or 0)
        total_doc = Decimal(cleaned.get("importe_total_doc") or 0)

        if total_doc < (total_sin + total_iva):
            self.add_error("importe_total_doc", _("El importe total del documento no puede ser menor a subtotal + IVA."))

        return cleaned


class RetencionImpuestoForm(forms.ModelForm):
    class Meta:
        model = RetencionImpuesto
        fields = ["codigo", "codigo_retencion", "base_imponible", "porcentaje_retener", "valor_retenido"]
        widgets = {
            "codigo": forms.Select(attrs={"class": "form-control"}),
            "codigo_retencion": forms.TextInput(attrs={"class": "form-control"}),
            "base_imponible": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "porcentaje_retener": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "valor_retenido": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "readonly": "readonly"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codigo"].choices = CODIGO_IMPUESTO_CHOICES


class RetencionCampoAdicionalForm(forms.ModelForm):
    class Meta:
        model = RetencionCampoAdicional
        fields = ["nombre", "valor"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "valor": forms.TextInput(attrs={"class": "form-control"}),
        }


RetencionImpuestoFormSet = inlineformset_factory(
    RetencionCompra,
    RetencionImpuesto,
    form=RetencionImpuestoForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)

RetencionCampoAdicionalFormSet = inlineformset_factory(
    RetencionCompra,
    RetencionCampoAdicional,
    form=RetencionCampoAdicionalForm,
    extra=1,
    can_delete=True,
)
