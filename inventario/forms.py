import datetime
from decimal import Decimal
from django import forms
from .models import Producto, Cliente, Proveedor, Usuario, Opciones, Secuencia, Facturador, Almacen, FormaPago, Banco, Caja, Empresa
from django.forms import ModelChoiceField
from django.core.exceptions import ValidationError

class MisProductos(ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s" % obj.descripcion

class MisPrecios(ModelChoiceField):
    def label_from_instance(self,obj):
        return "%s" % obj.precio

class MisDisponibles(ModelChoiceField):
    def label_from_instance(self,obj):
        return "%s" % obj.disponible

class LoginFormulario(forms.Form):
    identificacion = forms.CharField(
        label="Identificación",
        widget=forms.TextInput(attrs={
            'placeholder': 'Cédula o RUC',
            'class': 'form-control underlined',
            'type': 'text',
            'id': 'identificacion',
            'maxlength': '13',
            'pattern': '[0-9]*',
            'inputmode': 'numeric'
        })
    )

    empresa = forms.ModelChoiceField(
        label="Empresa",
        queryset=Empresa.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control underlined', 'id': 'empresa'})
    )

    def __init__(self, *args, **kwargs):
        empresas = kwargs.pop('empresas', None)
        super().__init__(*args, **kwargs)
        if empresas is not None:
            self.fields['empresa'].queryset = empresas

    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña', 'class': 'form-control underlined', 'id': 'password'})
    )

    def clean_identificacion(self):
        identificacion = self.cleaned_data.get('identificacion')
        if not identificacion.isdigit():
            raise ValidationError('La identificación solo debe contener números.')
        return identificacion


class ProductoFormulario(forms.ModelForm):
    # ✅ CORREGIDO: Opciones de IVA según tabla 17 SRI v2.31
    IVA_CHOICES = [
        ('0', '0%'),                    # ✅ Código SRI: 0
        ('5', '5%'),                    # ✅ Código SRI: 5
        ('2', '12%'),                   # ✅ CORREGIDO: era ('1', '12%') 
        ('10', '13%'),                  # ✅ CORREGIDO: era ('2', '13%')
        ('3', '14%'),                   # ✅ Código SRI: 3
        ('4', '15%'),                   # ✅ Código SRI: 4
        ('6', 'No Objeto'),             # ✅ Código SRI: 6
        ('7', 'Exento de IVA'),         # ✅ Código SRI: 7
        ('8', 'IVA Diferenciado'),      # ✅ CORREGIDO: era ('8', '8%')
    ]
    
    precio = forms.DecimalField(
        min_value=0,
        label='Precio',
        widget=forms.NumberInput(attrs={'placeholder': 'Precio del producto', 'id': 'precio', 'class': 'form-control'}),
    )

    precio2 = forms.DecimalField(
        min_value=0,
        label='Precio 2',
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Precio 2 (opcional)', 'id': 'precio2', 'class': 'form-control'}),
    )

    iva = forms.ChoiceField(
        choices=IVA_CHOICES,  # ✅ Usa las choices corregidas
        label='I.V.A:',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'iva'}),
    )

    class Meta:
        model = Producto
        fields = ['codigo', 'codigo_barras', 'descripcion', 'precio', 'precio2', 'categoria', 'disponible', 'iva', 'costo_actual']
        labels = {
            'descripcion': 'Descripción',
            'disponible': 'Disponible',
            'iva': 'I.V.A:',
            'costo_actual': 'Costo actual:',
        }
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'Código del producto', 'id': 'codigo', 'class': 'form-control'}),
            'codigo_barras': forms.TextInput(attrs={'placeholder': 'Código de barras del producto', 'id': 'codigo_barras', 'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'Descripción', 'id': 'descripcion', 'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control', 'id': 'categoria'}),
            'disponible': forms.NumberInput(attrs={'placeholder': 'Cantidad disponible', 'id': 'disponible', 'class': 'form-control'}),
            'costo_actual': forms.TextInput(attrs={'placeholder': 'Costo actual', 'id': 'costo_actual', 'class': 'form-control'}),
        }

    # Campos de solo lectura para mostrar el precio con IVA calculado
    precio_iva1 = forms.DecimalField(
        label='Precio IVA 1:',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'id': 'precio_iva1'}),
    )

    precio_iva2 = forms.DecimalField(
        label='Precio IVA 2:',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'id': 'precio_iva2'}),
    )

    def __init__(self, *args, empresa=None, **kwargs):
        self.empresa = empresa
        super(ProductoFormulario, self).__init__(*args, **kwargs)
        if self.instance.pk:
            # El formulario se utiliza para editar un producto existente
            self.calcular_precios_con_iva(self.instance.precio, self.instance.precio2, self.instance.iva)
        else:
            # El formulario es nuevo
            self.fields['precio_iva1'].initial = 0
            self.fields['precio_iva2'].initial = 0

    def calcular_precios_con_iva(self, precio, precio2, iva):
        """✅ CORREGIDO: Cálculo usando mapeo SRI correcto"""
        # ✅ CORRECCIÓN CRÍTICA: Mapeo exacto según tabla 17 SRI v2.31
        MAPEO_IVA_PORCENTAJES = {
            '0': 0.00,    # 0%
            '5': 0.05,    # 5%
            '2': 0.12,    # 12%
            '10': 0.13,   # 13%
            '3': 0.14,    # 14%
            '4': 0.15,    # 15%
            '6': 0.00,    # No objeto
            '7': 0.00,    # Exento
            '8': 0.08,    # IVA diferenciado
        }
        
        iva_percent = Decimal(str(MAPEO_IVA_PORCENTAJES.get(iva, 0.00)))
        self.fields['precio_iva1'].initial = precio * (Decimal('1.00') + iva_percent)
        if precio2:
            self.fields['precio_iva2'].initial = precio2 * (Decimal('1.00') + iva_percent)
        else:
            self.fields['precio_iva2'].initial = 0

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if self.empresa:
            qs = Producto.objects.filter(empresa=self.empresa, codigo=codigo)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('Ya existe un producto con este código en esta empresa.')
        return codigo
            
class ImportarClientesFormulario(forms.Form):
    importar = forms.FileField(
        max_length = 100000000000,
        label = 'Escoger archivo',
        widget = forms.ClearableFileInput(
        attrs={'id':'importar','class':'form-control'}),
        )

class ExportarProductosFormulario(forms.Form):
    desde = forms.DateField(
        label = 'Desde',
        widget = forms.DateInput(format=('%d-%m-%Y'),
        attrs={'id':'desde','class':'form-control','type':'date'}),
        )

    hasta = forms.DateField(
        label = 'Hasta',
        widget = forms.DateInput(format=('%d-%m-%Y'),
        attrs={'id':'hasta','class':'form-control','type':'date'}),
        )

class ExportarClientesFormulario(forms.Form):
    desde = forms.DateField(
        label = 'Desde',
        widget = forms.DateInput(format=('%d-%m-%Y'),
        attrs={'id':'desde','class':'form-control','type':'date'}),
        )

    hasta = forms.DateField(
        label = 'Hasta',
        widget = forms.DateInput(format=('%d-%m-%Y'),
        attrs={'id':'hasta','class':'form-control','type':'date'}),
        )

class ClienteFormulario(forms.ModelForm):
    TIPO_IDENTIFICACION_CHOICES = [
        ('04', 'RUC'),
        ('05', 'Cédula'),
        ('06', 'Pasaporte'),
        ('07', 'Consumidor Final'),
        ('08', 'Identificación del Exterior'),
    ]
    tipoV = [('1', 'Local'), ('2', 'Exportación')]
    tipoR = [('1', 'General'), ('2', 'Rimpe - Emprendedores'), ('3', 'Rimpe - Negocios Populares')]
    tipoCL = [('1', 'Persona Natural'), ('2', 'Sociedad')]

    tipoIdentificacion = forms.ChoiceField(
        label="Tipo de identificación",
        choices=TIPO_IDENTIFICACION_CHOICES,
        widget=forms.Select(attrs={
            'placeholder': 'Tipo de identificación', 
            'id': 'id_tipoIdentificacion', 
            'class': 'form-control'
        })
    )
    identificacion = forms.CharField(
        label="Número de Identificación",
        max_length=13,
        widget=forms.TextInput(attrs={
            'placeholder': 'Ingrese el número de identificación',
            'id': 'id_identificacion',
            'class': 'form-control',
            'pattern': '[0-9]*',
            'inputmode': 'numeric'
        })
    )
    razon_social = forms.CharField(
        label="Razón Social",
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': 'Ingrese la razón social',
            'id': 'id_razon_social',
            'class': 'form-control'
        })
    )
    nombre_comercial = forms.CharField(
        label="Nombre Comercial",
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Ingrese el nombre comercial',
            'id': 'id_apellido',
            'class': 'form-control'
        })
    )
    direccion = forms.CharField(
        label="Dirección",
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': 'Direccion del cliente', 
            'id': 'id_direccion', 
            'class': 'form-control'
        })
    )
    telefono = forms.CharField(
        label="Numero telefonico del cliente",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'El telefono del cliente', 
            'id': 'id_telefono', 
            'class': 'form-control',
            'pattern': '[0-9]*',
            'inputmode': 'numeric'
        })
    )
    correo = forms.CharField(
        label="Correo electronico del cliente",
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Correo del cliente', 
            'id': 'id_correo', 
            'class': 'form-control'
        })
    )
    observaciones = forms.CharField(
        label="Observaciones (Opcional)",
        max_length=300,
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Cualquier observacion adicional', 
            'id': 'id_observaciones', 
            'class': 'form-control',
            'rows': 3
        })
    )
    tipoVenta = forms.ChoiceField(
        label="Tipo de venta",
        choices=tipoV,
        widget=forms.Select(attrs={
            'placeholder': 'Tipo de venta', 
            'id': 'id_tipoVenta', 
            'class': 'form-control'
        })
    )
    tipoRegimen = forms.ChoiceField(
        label="Tipo de regimen",
        choices=tipoR,
        widget=forms.Select(attrs={
            'placeholder': 'Tipo de regimen', 
            'id': 'id_tipoRegimen', 
            'class': 'form-control'
        })
    )
    tipoCliente = forms.ChoiceField(
        label="Tipo de cliente",
        choices=tipoCL,
        widget=forms.Select(attrs={
            'placeholder': 'Tipo de cliente',
            'id': 'id_tipoCliente',
            'class': 'form-control'
        })
    )

    def __init__(self, *args, empresa=None, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)

    def clean_identificacion(self):
        identificacion = self.cleaned_data.get('identificacion')
        if self.empresa:
            qs = Cliente.objects.filter(empresa=self.empresa, identificacion=identificacion)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('Ya existe un cliente con esta identificación en esta empresa.')
        return identificacion

    class Meta:
        model = Cliente
        fields = [
            'tipoIdentificacion',
            'identificacion',
            'razon_social',
            'nombre_comercial',
            'direccion',
            'telefono',
            'correo',
            'observaciones',
            'convencional',
            'tipoVenta',
            'tipoRegimen',
            'tipoCliente'
        ]
        labels = {
            'tipoIdentificacion': 'Tipo de Identificación',
            'identificacion': 'Identificación',
            'razon_social': 'Razón Social',
            'nombre_comercial': 'Nombre Comercial',
            'direccion': 'Dirección',
            'telefono': 'Teléfono',
            'correo': 'Correo',
            'observaciones': 'Observaciones',
            'convencional': 'Convencional',
            'tipoVenta': 'Tipo de Venta',
            'tipoRegimen': 'Tipo de Régimen',
            'tipoCliente': 'Tipo de Cliente'
        }
        widgets = {
            'tipoIdentificacion': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipoIdentificacion'}),
            'identificacion': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_identificacion'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_razon_social'}),
            'nombre_comercial': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_nombre_comercial'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_direccion'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_telefono'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control', 'id': 'id_correo'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'id': 'id_observaciones'}),
            'convencional': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_convencional'}),
            'tipoVenta': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipoVenta'}),
            'tipoRegimen': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipoRegimen'}),
            'tipoCliente': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipoCliente'})
        }

    def clean(self):
        cleaned_data = super().clean()
        tipo_identificacion = cleaned_data.get('tipoIdentificacion')
        identificacion = cleaned_data.get('identificacion')
        if tipo_identificacion == '07':
            if identificacion != '9999999999999':
                self.add_error('identificacion', 'Para Consumidor Final, la identificación debe ser 9999999999999 (13 nueves).')
        else:
            if identificacion == '9999999999999':
                self.add_error('identificacion', 'La identificación 9999999999999 solo es válida para Consumidor Final.')
        return cleaned_data

class EmitirPedidoFormulario(forms.Form):
    """
    Formulario inicial para emitir un pedido a proveedor.
    La vista espera dos campos:
    - proveedor: identificación del proveedor (ChoiceField)
    - productos: cantidad de filas a generar en el formset de detalles (IntegerField)
    """

    def __init__(self, *args, **kwargs):
        cedulas = kwargs.pop('cedulas', [])  # Lista de pares [identificacion, etiqueta]
        super().__init__(*args, **kwargs)

        self.fields['proveedor'] = forms.ChoiceField(
            label="Seleccione Proveedor",
            choices=[(c[0], c[1]) for c in cedulas],
            widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_proveedor_select'})
        )

        self.fields['productos'] = forms.IntegerField(
            label="Número de productos",
            min_value=1,
            initial=1,
            widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_productos', 'min': '1'})
        )

    def clean_productos(self):
        productos = self.cleaned_data.get('productos')
        # Limitar a un rango razonable para evitar cargas excesivas
        if productos is None or productos < 1 or productos > 50:
            raise forms.ValidationError('Debe ingresar entre 1 y 50 productos.')
        return productos

class DetallesPedidoFormulario(forms.Form):
    """
    Formulario para cada línea del detalle del pedido.
    La vista consume los campos:
    - descripcion: Producto seleccionado (se usa .descripcion internamente)
    - cantidad: cantidad de productos
    - valor_subtotal: subtotal sin IVA para esa línea
    """

    descripcion = MisProductos(
        queryset=Producto.objects.none(),
        label='Producto',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_producto'})
    )
    cantidad = forms.IntegerField(
        label='Cantidad',
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_cantidad', 'min': '1'})
    )
    valor_subtotal = forms.DecimalField(
        label='Subtotal',
        min_value=Decimal('0.00'),
        max_digits=20,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_subtotal', 'step': '0.01', 'min': '0'})
    )

    def __init__(self, *args, **kwargs):
        empresa_id = kwargs.pop('empresa_id', None)
        super().__init__(*args, **kwargs)
        if empresa_id is not None:
            self.fields['descripcion'].queryset = Producto.objects.filter(
                empresa_id=empresa_id
            ).order_by('descripcion')

class EmitirFacturaFormulario(forms.Form):
    def __init__(self, *args, **kwargs):
        cedulas = kwargs.pop('cedulas', [])
        secuencias = kwargs.pop('secuencias', [])
        super().__init__(*args, **kwargs)

        # Campo para seleccionar secuencia
        # Construir las opciones de secuencia con un placeholder inicial '...'
        secuencia_choices = [('', '...')]
        secuencia_choices.extend([
            (s.id, f"{s.get_establecimiento_formatted()}-{s.get_punto_emision_formatted()}-{s.get_secuencial_formatted()} ({s.descripcion})")
            for s in secuencias
        ])
        self.fields['secuencia'] = forms.ChoiceField(
            label="Secuencia",
            choices=secuencia_choices,
            widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_secuencia'})
        )

        # Campo para el cliente con la lista de cédulas/RUCs
        self.fields['cliente'] = forms.ChoiceField(
            label="Seleccione Cliente",
            choices=[(c[0], c[1]) for c in cedulas],
            required=False,  # No requerido porque también hay búsqueda manual
            widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_cliente_select'})
        )

        # Campos para búsqueda manual de cliente
        self.fields['identificacion_cliente'] = forms.CharField(
            label="CI/RUC",
            max_length=13,
            required=False,  # Se llenará automáticamente
            widget=forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Cédula o RUC del cliente', 
                'id': 'id_identificacion_cliente'
            })
        )
        
        self.fields['nombre_cliente'] = forms.CharField(
            label="Nombre del Cliente",
            max_length=100,
            required=False,  # Se llenará automáticamente
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo del cliente',
                'readonly': 'readonly',
                'id': 'id_nombre_cliente'
            })
        )

        # Campo para el correo del cliente
        self.fields['correo_cliente'] = forms.EmailField(
            label="Correo del Cliente",
            required=True,
            widget=forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Correo del cliente',
                'id': 'id_correo_cliente'
            })
        )

    # Fechas
    fecha_emision = forms.DateField(
        label="Fecha de Emisión",
        widget=forms.DateInput(attrs={
            'type': 'date', 
            'class': 'form-control',
            'id': 'id_fecha_emision'
        })
    )
    
    fecha_vencimiento = forms.DateField(
        label="Fecha de Vencimiento",
        widget=forms.DateInput(attrs={
            'type': 'date', 
            'class': 'form-control',
            'id': 'id_fecha_vencimiento'
        })
    )

    # Campos de secuencia (se llenan automáticamente)
    establecimiento = forms.CharField(
        label="Establecimiento",
        max_length=3,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'readonly': 'readonly',
            'id': 'id_establecimiento'
        })
    )
    
    punto_emision = forms.CharField(
        label="Punto de Emisión",
        max_length=3,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'readonly': 'readonly',
            'id': 'id_punto_emision'
        })
    )
    
    secuencia_valor = forms.CharField(
        label="Número de Factura",
        max_length=9,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'id': 'id_secuencia_valor'
        })
    )

    # Otros campos
    concepto = forms.CharField(
        label="Concepto",
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3,
            'id': 'concepto',
            'placeholder': 'Concepto de la factura (opcional)'
        })
    )
    
    almacen = forms.ChoiceField(
        label="Almacén",
        choices=[],  # Se llenará dinámicamente en la vista
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'almacen'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        
        # Validar que se haya seleccionado un cliente de alguna forma
        cliente_id = self.data.get('cliente_id')  # Campo oculto del JavaScript
        cliente_select = cleaned_data.get('cliente')
        identificacion = cleaned_data.get('identificacion_cliente')
        
        if not cliente_id and not cliente_select and not identificacion:
            raise forms.ValidationError("Debe seleccionar un cliente.")

        # Validar fechas
        fecha_emision = cleaned_data.get('fecha_emision')
        fecha_vencimiento = cleaned_data.get('fecha_vencimiento')
        
        if fecha_emision and fecha_vencimiento:
            if fecha_vencimiento < fecha_emision:
                raise forms.ValidationError("La fecha de vencimiento no puede ser anterior a la fecha de emisión.")

        # Validar correo del cliente
        correo = cleaned_data.get('correo_cliente')
        if not correo:
            raise forms.ValidationError("El correo del cliente es obligatorio.")

        return cleaned_data

class EmitirProformaFormulario(forms.Form):
    """Formulario para emitir una proforma (cotización), sin pagos ni SRI."""
    # Datos del cliente (búsqueda manual similar a Factura)
    identificacion_cliente = forms.CharField(
        label="CI/RUC",
        max_length=13,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cédula o RUC del cliente',
            'id': 'id_identificacion_cliente',
        })
    )

    cliente_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={
            'id': 'cliente_id'
        })
    )

    nombre_cliente = forms.CharField(
        label="Nombre del Cliente",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre completo del cliente',
            'readonly': 'readonly',
            'id': 'id_nombre_cliente',
        })
    )

    correo_cliente = forms.EmailField(
        label="Correo del Cliente",
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Correo del cliente',
            'id': 'id_correo_cliente',
        })
    )

    # Fechas
    fecha_emision = forms.DateField(
        label="Fecha de Emisión",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'id_fecha_emision',
        })
    )

    fecha_validez = forms.DateField(
        label="Válida Hasta",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'id_fecha_validez',
        })
    )

    concepto = forms.CharField(
        label="Concepto",
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'id': 'id_concepto',
            'placeholder': 'Concepto de la proforma (opcional)'
        })
    )

    observaciones = forms.CharField(
        label="Observaciones",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'id': 'id_observaciones',
            'placeholder': 'Observaciones (opcional)'
        })
    )

    # Campos adicionales para la proforma
    almacen = forms.ModelChoiceField(
        label="Almacén",
        queryset=None,  # Se poblará dinámicamente en la vista
        required=False,
        empty_label="Seleccionar almacén...",
        widget=forms.Select(attrs={
            'class': 'border rounded px-2 py-1',
            'id': 'id_almacen',
        })
    )

    vendedor = forms.ModelChoiceField(
        label="Vendedor",
        queryset=None,  # Se poblará dinámicamente en la vista  
        required=False,
        empty_label="Seleccionar vendedor...",
        widget=forms.Select(attrs={
            'class': 'border rounded px-2 py-1',
            'id': 'id_vendedor',
        })
    )

    # Formas de pago disponibles para la proforma
    FORMAS_PAGO_CHOICES = [
        ('01', 'Efectivo'),
        ('20', 'Crédito'),
        ('04', 'Cheque'),
        ('19', 'Tarjeta de Crédito'),
        ('16', 'Depósito'),
    ]

    forma_pago = forms.ChoiceField(
        label="Forma de Pago",
        choices=FORMAS_PAGO_CHOICES,
        initial='01',  # Efectivo por defecto
        widget=forms.Select(attrs={
            'class': 'border rounded px-2 py-1',
            'id': 'id_forma_pago',
        })
    )

    def __init__(self, *args, **kwargs):
        # Extraer las opciones pasadas desde la vista
        almacenes = kwargs.pop('almacenes', None)
        vendedores = kwargs.pop('vendedores', None)
        super().__init__(*args, **kwargs)
        
        # Poblar los querysets si se proporcionaron
        if almacenes is not None:
            self.fields['almacen'].queryset = almacenes
        if vendedores is not None:
            self.fields['vendedor'].queryset = vendedores

    def clean(self):
        cleaned_data = super().clean()
        # Si se proporciona correo, validar que haya identificación o nombre (mínimo contexto)
        correo = cleaned_data.get('correo_cliente')
        ident = cleaned_data.get('identificacion_cliente')
        nombre = cleaned_data.get('nombre_cliente')
        if correo and not (ident or nombre):
            raise forms.ValidationError("Debe ingresar identificación o nombre del cliente si especifica correo.")
        return cleaned_data

class ProveedorFormulario(forms.ModelForm):
    # ✅ ACTUALIZADO: Ahora usa las mismas opciones que Cliente
    TIPO_IDENTIFICACION_CHOICES = [
        ('04', 'RUC'),
        ('05', 'Cédula'),
        ('06', 'Pasaporte'),
        ('07', 'Consumidor Final'),
        ('08', 'Identificación del Exterior'),
    ]
    tipoV = [('1', 'Local'), ('2', 'Exportación')]
    tipoR = [('1', 'General'), ('2', 'Rimpe - Emprendedores'), ('3', 'Rimpe - Negocios Populares')]
    tipoPR = [('1', 'Persona Natural'), ('2', 'Sociedad')]

    # ✅ NUEVO: Campo tipo identificación igual que Cliente
    tipoIdentificacion = forms.ChoiceField(
        label="Tipo de identificación",
        choices=TIPO_IDENTIFICACION_CHOICES,
        widget=forms.Select(attrs={
            'placeholder': 'Tipo de identificación', 
            'id': 'id_tipoIdentificacion', 
            'class': 'form-control'
        })
    )
    
    # ✅ ACTUALIZADO: Campo identificación ampliado
    identificacion_proveedor = forms.CharField(
        label="Número de Identificación",
        max_length=13,  # ✅ Ampliado de 12 a 13
        widget=forms.TextInput(attrs={
            'placeholder': 'Ingrese el número de identificación',
            'id': 'id_identificacion',
            'class': 'form-control',
            'pattern': '[0-9]*',
            'inputmode': 'numeric'
        })
    )
    
    # ✅ ACTUALIZADO: Razón social ampliada
    razon_social_proveedor = forms.CharField(
        label="Razón Social",
        max_length=200,  # ✅ Ampliado de 40 a 200
        widget=forms.TextInput(attrs={
            'placeholder': 'Ingrese la razón social',
            'id': 'id_razon_social',
            'class': 'form-control'
        })
    )
    
    # ✅ ACTUALIZADO: Nombre comercial ampliado
    nombre_comercial_proveedor = forms.CharField(
        label="Nombre Comercial",
        max_length=200,  # ✅ Ampliado de 40 a 200
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Ingrese el nombre comercial',
            'id': 'id_nombre_comercial',
            'class': 'form-control'
        })
    )
    
    # Campo dirección ya estaba bien
    direccion = forms.CharField(
        label="Dirección",
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': 'Direccion del proveedor', 
            'id': 'id_direccion', 
            'class': 'form-control'
        })
    )
    
    # ✅ ACTUALIZADO: Fecha nacimiento ahora opcional
    nacimiento = forms.DateField(
        label="Fecha de Nacimiento",
        required=False,  # ✅ Ahora es opcional
        widget=forms.DateInput(attrs={
            'id': 'id_nacimiento',
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    # Campo teléfono ya estaba bien
    telefono = forms.CharField(
        label="Numero telefonico del proveedor",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'El telefono del proveedor', 
            'id': 'id_telefono', 
            'class': 'form-control',
            'pattern': '[0-9]*',
            'inputmode': 'numeric'
        })
    )
    
    # Campo teléfono 2 ya estaba
    telefono2 = forms.CharField(
        required=False,
        label='Segundo numero telefonico (Opcional)',
        widget=forms.TextInput(
            attrs={'placeholder': 'Inserte el telefono alternativo del proveedor',
                   'id': 'telefono2', 'class': 'form-control'}),
    )
    
    # Campo correo principal
    correo = forms.CharField(
        label="Correo electronico del proveedor",
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Correo del proveedor', 
            'id': 'id_correo', 
            'class': 'form-control'
        })
    )

    # Campo correo 2 ya estaba
    correo2 = forms.CharField(
        required=False,
        label='Segundo correo electronico (Opcional)',
        widget=forms.TextInput(
            attrs={'placeholder': 'Inserte el correo alternativo del proveedor',
                   'id': 'correo2', 'class': 'form-control'}),
    )
    
    # ✅ NUEVOS CAMPOS (copiados desde ClienteFormulario)
    observaciones = forms.CharField(
        label="Observaciones (Opcional)",
        max_length=300,
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Cualquier observacion adicional', 
            'id': 'id_observaciones', 
            'class': 'form-control',
            'rows': 3
        })
    )
    
    convencional = forms.CharField(
        label="Teléfono Convencional (Opcional)",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Teléfono convencional', 
            'id': 'id_convencional', 
            'class': 'form-control'
        })
    )
    
    tipoVenta = forms.ChoiceField(
        label="Tipo de venta",
        choices=tipoV,
        widget=forms.Select(attrs={
            'placeholder': 'Tipo de venta', 
            'id': 'id_tipoVenta', 
            'class': 'form-control'
        })
    )
    
    tipoRegimen = forms.ChoiceField(
        label="Tipo de regimen",
        choices=tipoR,
        widget=forms.Select(attrs={
            'placeholder': 'Tipo de regimen', 
            'id': 'id_tipoRegimen', 
            'class': 'form-control'
        })
    )
    
    tipoProveedor = forms.ChoiceField(
        label="Tipo de proveedor",
        choices=tipoPR,
        widget=forms.Select(attrs={
            'placeholder': 'Tipo de proveedor',
            'id': 'id_tipoProveedor',
            'class': 'form-control'
        })
    )

    def __init__(self, *args, empresa=None, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)

    def clean_identificacion_proveedor(self):
        identificacion = self.cleaned_data.get('identificacion_proveedor')
        if self.empresa:
            qs = Proveedor.objects.filter(empresa=self.empresa, identificacion_proveedor=identificacion)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('Ya existe un proveedor con esta identificación en esta empresa.')
        return identificacion

    class Meta:
        model = Proveedor
        fields = [
            'tipoIdentificacion',
            'identificacion_proveedor', 
            'razon_social_proveedor', 
            'nombre_comercial_proveedor',
            'direccion', 
            'nacimiento', 
            'telefono', 
            'telefono2', 
            'correo', 
            'correo2',
            'observaciones',
            'convencional',
            'tipoVenta',
            'tipoRegimen',
            'tipoProveedor'
        ]
        labels = {
            'tipoIdentificacion': 'Tipo de Identificación',
            'identificacion_proveedor': 'Identificación del proveedor',
            'razon_social_proveedor': 'Razón Social del proveedor',
            'nombre_comercial_proveedor': 'Nombre Comercial del proveedor',
            'direccion': 'Dirección del proveedor',
            'nacimiento': 'Fecha de Nacimiento',
            'telefono': 'Numero telefonico del proveedor',
            'telefono2': 'Segundo numero telefonico',
            'correo': 'Correo electronico del proveedor',
            'correo2': 'Segundo correo electronico',
            'observaciones': 'Observaciones',
            'convencional': 'Teléfono Convencional',
            'tipoVenta': 'Tipo de Venta',
            'tipoRegimen': 'Tipo de Régimen',
            'tipoProveedor': 'Tipo de Proveedor'
        }
        widgets = {
            'tipoIdentificacion': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipoIdentificacion'}),
            'identificacion_proveedor': forms.TextInput(attrs={'placeholder': 'Inserte la cedula de identidad del proveedor',
                                                             'id': 'identificacion_proveedor', 'class': 'form-control'}),
            'razon_social_proveedor': forms.TextInput(attrs={'placeholder': 'Inserte el primer o primeros nombres del proveedor',
                                                           'id': 'razon_social_proveedor', 'class': 'form-control'}),
            'nombre_comercial_proveedor': forms.TextInput(attrs={'class': 'form-control', 'id': 'nombre_comercial_proveedor',
                                                               'placeholder': 'El apellido del proveedor'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'id': 'direccion',
                                              'placeholder': 'Direccion del proveedor'}),
            'nacimiento': forms.DateInput(attrs={'id': 'nacimiento', 'class': 'form-control',
                                                'type': 'date'}),
            'telefono': forms.TextInput(attrs={'id': 'telefono', 'class': 'form-control',
                                             'placeholder': 'El telefono del proveedor'}),
            'correo': forms.TextInput(attrs={'placeholder': 'Correo del proveedor',
                                           'id': 'correo', 'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'id': 'id_observaciones', 'rows': 3}),
            'convencional': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_convencional'}),
            'tipoVenta': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipoVenta'}),
            'tipoRegimen': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipoRegimen'}),
            'tipoProveedor': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipoProveedor'})
        }

    def clean(self):
        cleaned_data = super().clean()
        tipo_identificacion = cleaned_data.get('tipoIdentificacion')
        identificacion = cleaned_data.get('identificacion_proveedor')
        
        # ✅ NUEVA VALIDACIÓN: Misma que en Cliente
        if tipo_identificacion == '07':
            if identificacion != '9999999999999':
                self.add_error('identificacion_proveedor', 'Para Consumidor Final, la identificación debe ser 9999999999999 (13 nueves).')
        else:
            if identificacion == '9999999999999':
                self.add_error('identificacion_proveedor', 'La identificación 9999999999999 solo es válida para Consumidor Final.')
        return cleaned_data


class UsuarioFormulario(forms.Form):
    identificacion = forms.CharField(
        label = "Identificación",
        max_length=13,
        widget = forms.TextInput(attrs={'placeholder': 'Cédula o RUC',
        'id':'identificacion','class':'form-control','value':'','pattern':'[0-9]*','inputmode':'numeric'} ),
        )

    nombre_completo = forms.CharField(
        label = 'Nombre completo',
        max_length =150,
        widget = forms.TextInput(attrs={'placeholder': 'Inserte nombre y apellido',
        'id':'nombre_completo','class':'form-control','value':''}),
        )

    email = forms.EmailField(
        label='Correo electronico',
        max_length=100,
        widget=forms.EmailInput(
            attrs={
                'placeholder': 'Inserte un correo valido',
                'id': 'email',
                'class': 'form-control',
                'type': 'email',
                'value': '',
            }
        ),
    )

    level = forms.TypedChoiceField(
        required=False,
        label="Nivel de acceso",
        coerce=int,
        choices=[],
        widget=forms.Select(attrs={'placeholder': 'El nivel de acceso', 'id':'level','class':'form-control','value':''})
    )

    empresa = forms.ModelChoiceField(
        label="Empresa",
        queryset=Empresa.objects.none(),
        required=False,
        widget=forms.Select(attrs={'id':'empresa','class':'form-control'})
    )

    def __init__(self, *args, user=None, empresas_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if empresas_queryset is not None:
            self.fields['empresa'].queryset = empresas_queryset
        choices = [
            (Usuario.ADMIN, 'Administrador'),
            (Usuario.USER, 'Usuario'),
        ]
        if user and user.nivel == Usuario.ROOT:
            choices.insert(0, (Usuario.ROOT, 'Raiz'))
        self.fields['level'].choices = choices

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        return email

class NuevoUsuarioFormulario(forms.Form):
    identificacion = forms.CharField(
        label = "Identificación",
        max_length=13,
        widget = forms.TextInput(attrs={'placeholder': 'Cédula o RUC',
        'id':'identificacion','class':'form-control','value':'','pattern':'[0-9]*','inputmode':'numeric'} ),
        )

    nombre_completo = forms.CharField(
        label = 'Nombre completo',
        max_length =150,
        widget = forms.TextInput(attrs={'placeholder': 'Inserte nombre y apellido',
        'id':'nombre_completo','class':'form-control','value':''}),
        )

    email = forms.EmailField(
        label='Correo electronico',
        max_length=100,
        widget=forms.EmailInput(
            attrs={
                'placeholder': 'Inserte un correo valido',
                'id': 'email',
                'class': 'form-control',
                'type': 'email',
                'value': '',
            }
        ),
    )

    password = forms.CharField(
        label='Clave',
        max_length=100,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Inserte una clave',
                'id': 'password',
                'class': 'form-control',
                'value': '',
            }
        ),
    )

    rep_password = forms.CharField(
        label='Repetir clave',
        max_length=100,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Repita la clave de arriba',
                'id': 'rep_password',
                'class': 'form-control',
                'value': '',
            }
        ),
    )

    level = forms.TypedChoiceField(
        label="Nivel de acceso",
        coerce=int,
        choices=[],
        widget=forms.Select(attrs={'placeholder': 'El nivel de acceso', 'id':'level','class':'form-control','value':''})
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [
            (Usuario.ADMIN, 'Administrador'),
            (Usuario.USER, 'Usuario'),
        ]
        if user and user.nivel == Usuario.ROOT:
            choices.insert(0, (Usuario.ROOT, 'Raiz'))
        self.fields['level'].choices = choices

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        return email



class ClaveFormulario(forms.Form):
    #clave = forms.CharField(
        #label = 'Ingrese su clave actual',
        #max_length=50,
        #widget = forms.TextInput(
        #attrs={'placeholder': 'Inserte la clave actual para verificar su identidad',
        #'id':'clave','class':'form-control', 'type': 'password'}),
        #)

    clave_nueva = forms.CharField(
        label='Ingrese la clave nueva',
        max_length=50,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Inserte la clave nueva de acceso',
                'id': 'clave_nueva',
                'class': 'form-control',
            }
        ),
    )

    repetir_clave = forms.CharField(
        label="Repita la clave nueva",
        max_length=50,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Vuelva a insertar la clave nueva',
                'id': 'repetir_clave',
                'class': 'form-control',
            }
        ),
    )


class ImportarBDDFormulario(forms.Form):
    archivo = forms.FileField(
        widget=forms.FileInput(
            attrs={'placeholder': 'Archivo de la base de datos',
            'id':'customFile','class':'custom-file-input'})
        )

from django import forms
from .models import Opciones

class OpcionesFormulario(forms.Form):
    regimen = [('GENERAL', 'General'), ('RIMPE', 'RIMPE - EMPRENDEDORES')]
    obligacion = [('SI', 'SI'), ('NO', 'NO')]
    AGENTE_RETENCION_CHOICES = [
    ('...', '...'),
    ('NAC-GTRRIOC21-00000001', 'NAC-GTRRIOC21-00000001'),
    ('NAC-GTRRIOC22-00000001', 'NAC-GTRRIOC22-00000001'),
    ('NAC-GTRRIOC22-00000003', 'NAC-GTRRIOC22-00000003'),
    ('NAC-DGERCGC24-00000014', 'NAC-DGERCGC24-00000014'),
    ('NAC-DGERCGC25-00000010', 'NAC-DGERCGC25-00000010'),
]
    # Campos existentes (actualizados)
    identificacion = forms.CharField(
        label='RUC/Identificación',
        max_length=13,  # Cambiar de 20 a 13
        widget=forms.TextInput(attrs={
            'id': 'identificacion',
            'class': 'form-control',
            'placeholder': 'RUC de 13 dígitos',
            'readonly': True,
        }),
    )
    
    razon_social = forms.CharField(
        label='Razón social',
        max_length=300,  # Cambiar de 200 a 300
        widget=forms.TextInput(attrs={
            'id': 'razon_social', 
            'class': 'form-control'
        }),
    )
    
    nombre_comercial = forms.CharField(
        label='Nombre Comercial',
        max_length=300,  # Cambiar de 200 a 300
        widget=forms.TextInput(attrs={
            'id': 'nombre_comercial', 
            'class': 'form-control'
        }),
    )
    
    direccion_establecimiento = forms.CharField(
        label='Dirección',
        max_length=300,  # Cambiar de 200 a 300
        widget=forms.Textarea(attrs={
            'id': 'direccion', 
            'class': 'form-control',
            'rows': 3
        }),
    )
    
    correo = forms.EmailField(  # Cambiar a EmailField
        label='Correo electrónico',
        max_length=100,
        widget=forms.EmailInput(attrs={
            'id': 'correo', 
            'class': 'form-control'
        }),
    )
    
    telefono = forms.CharField(
        label='Telefono',
        max_length=20,
        widget=forms.TextInput(attrs={
            'id': 'telefono', 
            'class': 'form-control'
        }),
    )
    
    obligado = forms.CharField(
        label="Obligado a llevar contabilidad",
        max_length=2,
        widget=forms.Select(choices=obligacion, attrs={
            'id': 'obligado', 
            'class': 'form-control'
        })
    )
    
    tipo_regimen = forms.CharField(
        label="Régimen tributario",
        max_length=20,
        widget=forms.Select(choices=regimen, attrs={
            'id': 'tipo_regimen', 
            'class': 'form-control'
        })
    )
    
    moneda = forms.CharField(
        label='Moneda del sistema',
        max_length=20,
        widget=forms.HiddenInput(),
    )
    
    mensaje_factura = forms.CharField(
        label='Mensaje en facturas',
        max_length=200,
        widget=forms.Textarea(attrs={
            'id': 'mensaje_factura',
            'class': 'form-control',
            'rows': 2
        }),
    )
    
    nombre_negocio = forms.CharField(
        label='Nombre del negocio',
        max_length=25,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'nombre_negocio'
        }),
    )
    
    # NUEVOS CAMPOS SRI
    es_contribuyente_especial = forms.BooleanField(
        label='¿Es contribuyente especial?',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'es_contribuyente_especial'
        })
    )
    
    numero_contribuyente_especial = forms.CharField(
        label='Número de resolución',
        max_length=13,
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'numero_contribuyente_especial',
            'class': 'form-control',
            'placeholder': 'Número de resolución'
        })
    )
    
    es_agente_retencion = forms.BooleanField(
        label='¿Es agente de retención?',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'es_agente_retencion'
        })
    )

    numero_agente_retencion = forms.ChoiceField(
        label='Número de resolución',
        choices=AGENTE_RETENCION_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'id': 'numero_agente_retencion',
            'class': 'form-control'
        })
    )
    
    imagen = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'custom-file-input',
            'id': 'customFile'
        })
    )
from django import forms
from .models import Secuencia

class SecuenciaFormulario(forms.ModelForm):
    secuencial = forms.IntegerField(
        label='Secuencial',
        min_value=1,
        max_value=999999999,
        widget=forms.NumberInput(attrs={
            'id': 'id_secuencial',
            'class': 'form-control',
            'placeholder': '1',
            'min': '1',
            'max': '999999999'
        })
    )

    establecimiento = forms.IntegerField(
        label='Establecimiento',
        min_value=1,
        max_value=999,
        widget=forms.NumberInput(attrs={
            'id': 'id_establecimiento',
            'class': 'form-control',
            'placeholder': '1',
            'min': '1',
            'max': '999'
        })
    )

    punto_emision = forms.IntegerField(
        label='Punto de Emisión',
        min_value=1,
        max_value=999,
        widget=forms.NumberInput(attrs={
            'id': 'id_punto_emision',
            'class': 'form-control',
            'placeholder': '1',
            'min': '1',
            'max': '999'
        })
    )

    class Meta:
        model = Secuencia
        fields = [
            'descripcion',
            'tipo_documento',
            'secuencial',
            'establecimiento',
            'punto_emision',
            'activo',
            'iva',
            'fiscal',
            'documento_electronico'
        ]
        labels = {
            'descripcion': 'Descripción',
            'tipo_documento': 'Tipo de Documento',
            'secuencial': 'Secuencial',
            'establecimiento': 'Establecimiento',
            'punto_emision': 'Punto de Emisión',
            'activo': 'Activo',
            'iva': 'IVA',
            'fiscal': 'Fiscal',
            'documento_electronico': 'Documento Electrónico'
        }
        widgets = {
            'descripcion': forms.TextInput(
                attrs={
                    'placeholder': 'Descripción del documento',
                    'id': 'descripcion',
                    'class': 'form-control'
                }
            ),
            'tipo_documento': forms.Select(
                choices=[
                    ('01', 'Factura'),
                    ('03', 'Liquidación de Compra'),
                    ('04', 'Nota de Crédito'),
                    ('05', 'Nota de Débito'),
                    ('06', 'Guía de Remisión'),
                    ('07', 'Retención')
                ],
                attrs={
                    'id': 'tipo_documento',
                    'class': 'form-control'
                }
            ),
            'activo': forms.CheckboxInput(
                attrs={
                    'id': 'activo',
                    'class': 'form-check-input'
                }
            ),
            'iva': forms.CheckboxInput(
                attrs={
                    'id': 'iva',
                    'class': 'form-check-input'
                }
            ),
            'fiscal': forms.CheckboxInput(
                attrs={
                    'id': 'fiscal',
                    'class': 'form-check-input'
                }
            ),
            'documento_electronico': forms.CheckboxInput(
                attrs={
                    'id': 'documento_electronico',
                    'class': 'form-check-input'
                }
            ),
        }

    def clean_secuencial(self):
        secuencial = self.cleaned_data.get('secuencial')
        if secuencial and secuencial > 999999999:
            raise forms.ValidationError("El número secuencial no puede exceder los 9 dígitos.")
        return secuencial

    def clean_establecimiento(self):
        establecimiento = self.cleaned_data.get('establecimiento')
        if establecimiento and (establecimiento < 1 or establecimiento > 999):
            raise forms.ValidationError("El código de establecimiento debe estar entre 1 y 999.")
        return establecimiento

    def clean_punto_emision(self):
        punto_emision = self.cleaned_data.get('punto_emision')
        if punto_emision and (punto_emision < 1 or punto_emision > 999):
            raise forms.ValidationError("El código de punto de emisión debe estar entre 1 y 999.")
        return punto_emision
    

class FacturadorForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese la contraseña'
        }),
        label='Contraseña',
        min_length=8,
        required=False,  # No obligatorio al editar
        error_messages={
            'min_length': 'La contraseña debe tener al menos 8 caracteres.',
        }
    )
    verificar_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Verifique la contraseña'
        }),
        label='Verificar Contraseña',
        required=False  # No obligatorio al editar
    )
    nombres = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese el nombre completo'
        }),
        label='Nombres',
        max_length=255,
        error_messages={
            'required': 'El campo nombres es obligatorio.',
        }
    )
    telefono = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese el teléfono'
        }),
        label='Teléfono',
        max_length=15,
        required=False
    )
    correo = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese el correo electrónico'
        }),
        label='Correo',
        error_messages={
            'required': 'El correo electrónico es obligatorio.',
            'invalid': 'Ingrese un correo válido.',
        }
    )
    descuento_permitido = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese el descuento permitido'
        }),
        label='Descuento Permitido',
        max_digits=5,
        decimal_places=2
    )
    activo = forms.BooleanField(
        required=False,
        initial=True,
        label='Activo',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    class Meta:
        model = Facturador
        fields = [
            'nombres',
            'telefono',
            'correo',
            'descuento_permitido',
            'activo',
        ]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        verificar_password = cleaned_data.get("verificar_password")

        # Si se proporciona una contraseña, validar que coincidan
        if password or verificar_password:
            if password != verificar_password:
                raise forms.ValidationError("Las contraseñas no coinciden. Inténtelo de nuevo.")

        return cleaned_data

    def save(self, commit=True):
        facturador = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            facturador.set_password(password)
        if commit:
            facturador.save()
        return facturador

class AlmacenForm(forms.ModelForm):
    class Meta:
        model = Almacen
        fields = ['descripcion', 'activo']
        labels = {
            'descripcion': 'Descripción del Almacén',
            'activo': '¿Está activo?',
        }
        widgets = {
            'descripcion': forms.TextInput(attrs={
                'class': 'border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-48 py-1 px-2 text-sm h-8'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500'
            })
        }

# === PLACEHOLDER FORMS (para evitar errores mientras se refactoriza) ===
class ImportarProductosFormulario(forms.Form):
    archivo = forms.FileField(required=False, help_text="CSV/XLSX de productos")

class ImportarProveedoresFormulario(forms.Form):
    archivo = forms.FileField(required=False, help_text="CSV/XLSX de proveedores")

class ExportarProveedoresFormulario(forms.Form):
    incluir_inactivos = forms.BooleanField(required=False, initial=False)

# ✅ FORMULARIO PARA FORMAS DE PAGO
class FormaPagoFormulario(forms.ModelForm):
    """
    Formulario para las formas de pago de facturas
    """
    
    class Meta:
        model = FormaPago
        fields = ['forma_pago', 'caja', 'total', 'plazo', 'unidad_tiempo']
        
        widgets = {
            'forma_pago': forms.Select(attrs={
                'class': 'form-control',
                'id': 'sri-pago-select'
            }),
            'caja': forms.Select(attrs={
                'class': 'form-control', 
                'id': 'caja-select'
            }),
            'total': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'plazo': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1',
                'min': '0',
                'placeholder': 'Días de plazo (opcional)'
            }),
            'unidad_tiempo': forms.Select(attrs={
                'class': 'form-control'
            })
        }
        
        labels = {
            'forma_pago': 'SRI Pago',
            'caja': 'Caja',
            'total': 'Valor',
            'plazo': 'Plazo',
            'unidad_tiempo': 'Unidad de Tiempo'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Hacer plazo y unidad_tiempo opcionales
        self.fields['plazo'].required = False
        self.fields['unidad_tiempo'].required = False
        
        # Agregar clases CSS adicionales
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
    
    def clean(self):
        cleaned_data = super().clean()
        plazo = cleaned_data.get('plazo')
        unidad_tiempo = cleaned_data.get('unidad_tiempo')
        
        # Si hay plazo, debe haber unidad de tiempo
        if plazo and not unidad_tiempo:
            raise forms.ValidationError('Debe especificar la unidad de tiempo cuando hay plazo')
        
        return cleaned_data

# ===============================  FORMULARIO BANCO  ===============================

class BancoFormulario(forms.ModelForm):
    """
    Formulario para crear/editar cuentas bancarias
    Campos según tu imagen del formulario
    """
    
    banco = forms.CharField(
        label='Banco',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre del banco (ej: Banco Pichincha)',
            'id': 'banco'
        }),
        help_text='Nombre completo del banco'
    )
    
    titular = forms.CharField(
        label='Titular',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre completo del titular',
            'id': 'titular'
        }),
        help_text='Nombre completo del titular de la cuenta'
    )
    
    numero_cuenta = forms.CharField(
        label='Número de Cuenta',
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número de cuenta bancaria',
            'id': 'numero_cuenta',
            'pattern': '[0-9\\-]+',
            'title': 'Solo números y guiones'
        }),
        help_text='Número de la cuenta bancaria (solo números y guiones)'
    )
    
    activo = forms.BooleanField(
        label='Activo',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'activo'
        }),
        help_text='¿La cuenta está activa para usar?'
    )
    
    saldo_inicial = forms.DecimalField(
        label='Saldo Inicial',
        min_value=0,
        initial=0.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'id': 'saldo_inicial',
            'step': '0.01'
        }),
        help_text='Saldo inicial de la cuenta bancaria'
    )
    
    tipo_cuenta = forms.ChoiceField(
        label='Tipo de Cuenta',
        choices=[
            ('CORRIENTE', 'Corriente'),
            ('AHORROS', 'Ahorros'),
            ('VISTA', 'Vista'),
            ('PLAZO_FIJO', 'Plazo Fijo'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'tipo_cuenta'
        }),
        help_text='Tipo de cuenta bancaria'
    )
    
    fecha_apertura = forms.DateField(
        label='Fecha Apertura',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'id': 'fecha_apertura'
        }),
        help_text='Fecha en que se abrió la cuenta'
    )
    
    telefono = forms.CharField(
        label='Teléfono',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Teléfono del banco (opcional)',
            'id': 'telefono',
            'pattern': '[0-9\\s\\-\\(\\)]+',
            'title': 'Solo números, espacios, guiones y paréntesis'
        }),
        help_text='Teléfono de contacto del banco (opcional)'
    )
    
    secuencial_cheque = forms.IntegerField(
        label='Secuencial Cheque',
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'id': 'secuencial_cheque'
        }),
        help_text='Próximo número de cheque a utilizar'
    )
    
    
    observaciones = forms.CharField(
        label='Observaciones',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Notas adicionales sobre la cuenta (opcional)',
            'id': 'observaciones'
        }),
        help_text='Notas adicionales sobre la cuenta bancaria'
    )
    
    class Meta:
        model = Banco
        fields = [
            'banco',
            'titular', 
            'numero_cuenta',
            'activo',
            'tipo_cuenta',
            'fecha_apertura',
            'telefono',
            'secuencial_cheque',
            'observaciones'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Establecer fecha actual por defecto si es un nuevo banco
        if not self.instance.pk:
            from datetime import date
            self.fields['fecha_apertura'].initial = date.today()
        
        # Agregar clases CSS a todos los campos si no las tienen
        for field_name, field in self.fields.items():
            if field_name == 'activo':
                continue  # El checkbox ya tiene su clase
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
    
    def clean_numero_cuenta(self):
        """Validación personalizada para número de cuenta"""
        numero_cuenta = self.cleaned_data.get('numero_cuenta')
        
        if numero_cuenta:
            # Limpiar espacios
            numero_cuenta = numero_cuenta.strip()
            
            # Verificar que no exista otra cuenta con el mismo número
            existe = Banco.objects.filter(numero_cuenta=numero_cuenta)
            if self.instance.pk:
                existe = existe.exclude(pk=self.instance.pk)
            
            if existe.exists():
                raise forms.ValidationError('Ya existe una cuenta con este número.')
            
            # Validar formato (solo números y guiones)
            import re
            if not re.match(r'^[0-9\-]+$', numero_cuenta):
                raise forms.ValidationError('El número de cuenta solo puede contener números y guiones.')
        
        return numero_cuenta
    
    def clean_telefono(self):
        """Validación personalizada para teléfono"""
        telefono = self.cleaned_data.get('telefono')
        
        if telefono:
            # Limpiar espacios
            telefono = telefono.strip()
            
            # Validar formato
            import re
            if not re.match(r'^[0-9\s\-\(\)]+$', telefono):
                raise forms.ValidationError(
                    'El teléfono solo puede contener números, espacios, guiones y paréntesis.'
                )
        
        return telefono
    
    def clean_banco(self):
        """Validación personalizada para nombre del banco"""
        banco = self.cleaned_data.get('banco')
        
        if banco:
            # Limpiar espacios extra
            banco = ' '.join(banco.split())
            
            # Capitalizar correctamente
            banco = banco.title()
        
        return banco
    
    def clean_titular(self):
        """Validación personalizada para titular"""
        titular = self.cleaned_data.get('titular')
        
        if titular:
            # Limpiar espacios extra
            titular = ' '.join(titular.split())
            
            # Convertir a mayúsculas (es común en bancos)
            titular = titular.upper()
        
        return titular
    
    def clean_secuencial_cheque(self):
        """Validación para secuencial de cheque"""
        secuencial = self.cleaned_data.get('secuencial_cheque')
        
        if secuencial and secuencial < 1:
            raise forms.ValidationError('El secuencial de cheque debe ser mayor a 0.')
        
        return secuencial
    


class CajaFormulario(forms.ModelForm):
    """
    Formulario para crear/editar cajas
    """
    
    descripcion = forms.CharField(
        label='Descripción',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Descripción de la caja',
            'id': 'descripcion'
        }),
        help_text='Descripción identificativa de la caja'
    )
    
    activo = forms.BooleanField(
        label='Activo',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'activo'
        }),
        help_text='Marcar si la caja está activa'
    )
    
    class Meta:
        model = Caja
        fields = ['descripcion', 'activo']
    
    def clean_descripcion(self):
        """Validación para descripción"""
        descripcion = self.cleaned_data.get('descripcion')
        
        if descripcion:
            descripcion = descripcion.strip()
            if len(descripcion) < 3:
                raise forms.ValidationError('La descripción debe tener al menos 3 caracteres.')
        
        return descripcion
class FirmaElectronicaForm(forms.ModelForm):
    class Meta:
        model = Opciones
        fields = [
            'tipo_ambiente',
            'tipo_emision',
            'numero_contribuyente_especial',
            'fecha_caducidad_firma',
            'password_firma',
            'obligado',
            'correo',
            'mensaje_factura',
            'firma_electronica',
        ]
        widgets = {
            'firma_electronica': forms.FileInput(attrs={'class': 'form-control'}),
            'password_firma': forms.PasswordInput(attrs={
                'class': 'form-control',
                'autocomplete': 'new-password',  # <-- Esto evita el autocompletado
                'placeholder': 'Ingrese la contraseña de la firma',
            }),
        }

    def clean_password_firma(self):
        password = self.cleaned_data.get('password_firma')
        if password not in (None, ''):
            return password

        if self.instance and getattr(self.instance, 'password_firma', None):
            return self.instance.password_firma

        return password

from django import forms
from .models import Servicio

class ServicioFormulario(forms.ModelForm):
    IVA_CHOICES = [
        ('0', '0%'),
        ('5', '5%'),
        ('2', '12%'),
        ('10', '13%'),
        ('3', '14%'),
        ('4', '15%'),
        ('6', 'No Objeto'),
        ('7', 'Exento de IVA'),
        ('8', 'IVA Diferenciado'),
    ]

    codigo = forms.CharField(
        label="Código",
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código del servicio'}),
    )
    descripcion = forms.CharField(
        label="Descripción",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Descripción del servicio', 'rows': 2}),
    )
    iva = forms.ChoiceField(
        choices=IVA_CHOICES,
        label="I.V.A:",
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    precio1 = forms.DecimalField(
        label="Precio 1",
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Precio 1'}),
    )
    precio2 = forms.DecimalField(
        label="Precio 2",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Precio 2 (opcional)'}),
    )
    activo = forms.BooleanField(
        label="Activo",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = Servicio
        fields = ['codigo', 'descripcion', 'iva', 'precio1', 'precio2', 'activo']