"""Formularios para Notas de Débito."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from inventario.models import Factura

from .models import NotaDebito, DetalleNotaDebito


class NotaDebitoForm(forms.ModelForm):
    class Meta:
        model = NotaDebito
        fields = [
            'factura_modificada',
            'fecha_emision',
            'motivo',
        ]
        widgets = {
            'fecha_emision': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'maxlength': 300}),
        }

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa

        if empresa:
            self.fields['factura_modificada'].queryset = Factura.objects.filter(
                empresa=empresa,
                estado_sri__in=['AUTORIZADO', 'AUTORIZADA'],
            ).order_by('-fecha_emision')

        self.fields['factura_modificada'].widget.attrs.update({'class': 'form-control'})
        self.fields['factura_modificada'].empty_label = '-- Seleccione una factura --'

    def clean_factura_modificada(self):
        factura = self.cleaned_data.get('factura_modificada')
        if not factura:
            raise ValidationError('Debe seleccionar una factura.')
        if factura.estado_sri not in ['AUTORIZADO', 'AUTORIZADA']:
            raise ValidationError('Solo puede emitir Nota de Débito para facturas autorizadas.')
        return factura


class DetalleNotaDebitoForm(forms.ModelForm):
    class Meta:
        model = DetalleNotaDebito
        fields = [
            'codigo_principal',
            'descripcion',
            'cantidad',
            'precio_unitario',
            'descuento',
            'codigo_iva',
            'tarifa_iva',
        ]
        widgets = {
            'codigo_principal': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'descuento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'codigo_iva': forms.Select(attrs={'class': 'form-control'}),
            'tarifa_iva': forms.NumberInput(attrs={'class': 'form-control', 'readonly': True}),
        }
