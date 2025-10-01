"""Formularios para la emisión de Liquidaciones de Compra."""
from __future__ import annotations

from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import (
    LiquidacionCampoAdicional,
    LiquidacionCompra,
    LiquidacionDetalle,
    LiquidacionFormaPago,
)


class LiquidacionCompraForm(forms.ModelForm):
    fecha_emision = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = LiquidacionCompra
        fields = [
            "proveedor",
            "almacen",
            "fecha_emision",
            "establecimiento",
            "punto_emision",
            "secuencia",
            "concepto",
            "observaciones",
            "sustento_tributario",
            "propina",
            "moneda",
        ]
        widgets = {
            "proveedor": forms.Select(attrs={"class": "form-control"}),
            "almacen": forms.Select(attrs={"class": "form-control"}),
            "establecimiento": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 999}),
            "punto_emision": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 999}),
            "secuencia": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 999999999}),
            "concepto": forms.TextInput(attrs={"class": "form-control"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "sustento_tributario": forms.Select(attrs={"class": "form-control"}),
            "propina": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "moneda": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_propina(self):
        propina = self.cleaned_data.get("propina", Decimal("0.00"))
        if propina < 0:
            raise forms.ValidationError("La propina no puede ser negativa.")
        return propina


class LiquidacionDetalleForm(forms.ModelForm):
    class Meta:
        model = LiquidacionDetalle
        fields = [
            "producto",
            "servicio",
            "descripcion",
            "unidad_medida",
            "cantidad",
            "costo",
            "descuento",
        ]
        widgets = {
            "producto": forms.Select(attrs={"class": "form-control"}),
            "servicio": forms.Select(attrs={"class": "form-control"}),
            "descripcion": forms.TextInput(attrs={"class": "form-control"}),
            "unidad_medida": forms.TextInput(attrs={"class": "form-control"}),
            "cantidad": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "costo": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "descuento": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def clean(self):
        cleaned = super().clean()
        producto = cleaned.get("producto")
        servicio = cleaned.get("servicio")
        descripcion = cleaned.get("descripcion")
        if not descripcion:
            if producto:
                cleaned["descripcion"] = producto.descripcion
            elif servicio:
                cleaned["descripcion"] = servicio.descripcion
            else:
                raise forms.ValidationError("Debe ingresar una descripción o seleccionar un producto/servicio.")
        if producto and servicio:
            raise forms.ValidationError("Seleccione producto o servicio, no ambos.")
        return cleaned


class LiquidacionFormaPagoForm(forms.ModelForm):
    class Meta:
        model = LiquidacionFormaPago
        fields = ["forma_pago", "total", "plazo", "unidad_tiempo"]
        widgets = {
            "forma_pago": forms.Select(attrs={"class": "form-control"}),
            "total": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "plazo": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "unidad_tiempo": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_total(self):
        total = self.cleaned_data.get("total")
        if total is None or total <= 0:
            raise forms.ValidationError("El total debe ser mayor que cero.")
        return total

    def clean(self):
        cleaned = super().clean()
        plazo = cleaned.get("plazo")
        unidad = cleaned.get("unidad_tiempo")
        if plazo and not unidad:
            raise forms.ValidationError("Debe indicar la unidad de tiempo cuando existe plazo.")
        return cleaned


DetalleFormSet = inlineformset_factory(
    LiquidacionCompra,
    LiquidacionDetalle,
    form=LiquidacionDetalleForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)

FormaPagoFormSet = inlineformset_factory(
    LiquidacionCompra,
    LiquidacionFormaPago,
    form=LiquidacionFormaPagoForm,
    extra=2,
    can_delete=True,
    min_num=1,
    validate_min=True,
)

CampoAdicionalFormSet = inlineformset_factory(
    LiquidacionCompra,
    LiquidacionCampoAdicional,
    fields=["nombre", "valor"],
    widgets={
        "nombre": forms.TextInput(attrs={"class": "form-control"}),
        "valor": forms.TextInput(attrs={"class": "form-control"}),
    },
    extra=1,
    can_delete=True,
    max_num=15,
)
