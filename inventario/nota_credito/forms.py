"""
Formularios para Notas de Crédito
"""
from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import NotaCredito, DetalleNotaCredito
from inventario.models import Factura


class NotaCreditoForm(forms.ModelForm):
    """Formulario principal para crear Nota de Crédito"""
    
    class Meta:
        model = NotaCredito
        fields = [
            'factura_modificada',
            'fecha_emision',
            'tipo_motivo',
            'motivo',
        ]
        widgets = {
            'fecha_emision': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'tipo_motivo': forms.Select(
                attrs={'class': 'form-control', 'id': 'tipo_motivo'}
            ),
            'motivo': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'placeholder': 'Describa el motivo de la nota de crédito...',
                    'maxlength': 300
                }
            ),
        }
    
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        
        # Filtrar facturas por empresa y estado AUTORIZADO
        if empresa:
            self.fields['factura_modificada'].queryset = Factura.objects.filter(
                empresa=empresa,
                estado_sri='AUTORIZADO'
            ).order_by('-fecha_emision')
        
        # Personalizar el widget de factura
        self.fields['factura_modificada'].widget.attrs.update({
            'class': 'form-control',
            'id': 'factura_modificada'
        })
        self.fields['factura_modificada'].label = 'Factura a Modificar'
        self.fields['factura_modificada'].empty_label = '-- Seleccione una factura --'
    
    def clean_factura_modificada(self):
        factura = self.cleaned_data.get('factura_modificada')
        
        if not factura:
            raise ValidationError('Debe seleccionar una factura.')
        
        if factura.estado_sri != 'AUTORIZADO':
            raise ValidationError('Solo puede emitir NC para facturas autorizadas.')
        
        # Verificar saldo disponible
        saldo = factura.saldo_para_nc
        if saldo <= 0:
            raise ValidationError('Esta factura ya no tiene saldo disponible para notas de crédito.')
        
        return factura
    
    def clean(self):
        cleaned_data = super().clean()
        tipo_motivo = cleaned_data.get('tipo_motivo')
        motivo = cleaned_data.get('motivo')
        
        # Si el motivo está vacío, usar el tipo como descripción
        if not motivo and tipo_motivo:
            motivo_dict = dict(NotaCredito.MOTIVO_CHOICES)
            cleaned_data['motivo'] = motivo_dict.get(tipo_motivo, 'Nota de crédito')
        
        return cleaned_data


class BuscarFacturaForm(forms.Form):
    """Formulario para buscar factura por número o cliente"""
    
    busqueda = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por número de factura, cliente o RUC...'
        })
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )


class DetalleNotaCreditoForm(forms.ModelForm):
    """Formulario para cada detalle de la NC"""
    
    class Meta:
        model = DetalleNotaCredito
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
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': True}),
            'descuento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'codigo_iva': forms.Select(attrs={'class': 'form-control'}),
            'tarifa_iva': forms.NumberInput(attrs={'class': 'form-control', 'readonly': True}),
        }
    
    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad and cantidad <= 0:
            raise ValidationError('La cantidad debe ser mayor a cero.')
        return cantidad


class SeleccionProductosForm(forms.Form):
    """
    Formulario dinámico para seleccionar qué productos de la factura incluir en la NC
    Se genera dinámicamente según los detalles de la factura
    """
    
    def __init__(self, *args, factura=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if factura:
            for detalle in factura.detallefactura_set.all():
                # Checkbox para incluir el producto
                self.fields[f'incluir_{detalle.id}'] = forms.BooleanField(
                    required=False,
                    initial=True,
                    label=detalle.producto.descripcion if detalle.producto else detalle.servicio.descripcion if detalle.servicio else 'Item'
                )
                
                # Campo de cantidad (máximo la cantidad original)
                self.fields[f'cantidad_{detalle.id}'] = forms.DecimalField(
                    required=False,
                    initial=detalle.cantidad,
                    max_value=detalle.cantidad,
                    min_value=Decimal('0.01'),
                    decimal_places=2,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control form-control-sm',
                        'step': '0.01',
                        'max': str(detalle.cantidad)
                    })
                )
