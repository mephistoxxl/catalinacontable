"""Formularios para la emisión de Liquidaciones de Compra."""
from __future__ import annotations

from decimal import Decimal

from django import forms
from django.core.validators import RegexValidator
from django.db.models import Q
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from ..models import Almacen, Proveedor
from .models import (
    LiquidacionCampoAdicional,
    LiquidacionCompra,
    LiquidacionDetalle,
    LiquidacionFormaPago,
)


class LiquidacionCompraForm(forms.ModelForm):
    secuencia_config_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    retencion_iva_porcentaje = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=4,
        initial=Decimal("1.0000"),
        widget=forms.HiddenInput(),
    )
    retencion_renta_porcentaje = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=4,
        initial=Decimal("0.0000"),
        widget=forms.HiddenInput(),
    )
    beneficiario_tipo_identificacion = forms.ChoiceField(
        label=_("Tipo de identificación"),
        choices=[
            ("05", _("Cédula")),
            ("06", _("Pasaporte")),
            ("08", _("Identificación del exterior")),
            ("07", _("Consumidor final")),
            ("04", _("RUC")),
        ],
        initial="05",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    beneficiario_identificacion = forms.CharField(
        label=_("C.I. / Identificación"),
        max_length=10,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "maxlength": "10",
                "minlength": "10",
                "inputmode": "numeric",
                "pattern": r"\d{10}",
                "placeholder": _("Ingrese cédula (10 dígitos)"),
            }
        ),
    )
    beneficiario_nombre = forms.CharField(
        label=_("Nombre / Razón social"),
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Nombres y apellidos del liquidado"),
            }
        ),
    )
    beneficiario_direccion = forms.CharField(
        label=_("Domicilio"),
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Provincia / Cantón / Dirección"),
            }
        ),
    )
    beneficiario_correo = forms.EmailField(
        label=_("Correo"),
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Opcional"),
            }
        ),
    )
    beneficiario_telefono = forms.CharField(
        label=_("Teléfono"),
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Opcional"),
            }
        ),
    )

    tipo_liquidacion = forms.ChoiceField(
        label=_("Liquidación"),
        choices=LiquidacionCompra.TIPO_LIQUIDACION_CHOICES,
        initial=LiquidacionCompra.TIPO_LIQUIDACION_CHOICES[0][0],
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    autorizacion = forms.CharField(
        label=_("Autorización"),
        required=False,
        max_length=50,
        validators=[
            RegexValidator(
                regex=r"^[0-9A-Za-z\s\-]+$",
                message=_("La autorización solo puede contener letras, números, espacios o guiones."),
            )
        ],
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Ingrese el código de autorización"),
            }
        ),
    )

    fecha_emision = forms.DateField(
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    forma_pago_simple = forms.ChoiceField(
        label=_("Forma de pago"),
        choices=[
            ("01", _("Efectivo")),
            ("16", _("Tarjeta débito")),
            ("19", _("Tarjeta crédito")),
            ("17", _("Dinero electrónico")),
            ("20", _("Crédito")),
        ],
        initial="01",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = LiquidacionCompra
        fields = [
            "proveedor",
            "almacen",
            "fecha_emision",
            "forma_pago_simple",
            "establecimiento",
            "punto_emision",
            "secuencia",
            "tipo_liquidacion",
            "concepto",
            "autorizacion",
            "observaciones",
            "sustento_tributario",
            "retencion_iva_porcentaje",
            "retencion_renta_porcentaje",
        ]
        widgets = {
            "proveedor": forms.HiddenInput(),
            "almacen": forms.Select(attrs={"class": "form-control"}),
            "establecimiento": forms.TextInput(
                attrs={
                    "class": "form-control text-right",
                    "maxlength": "3",
                    "pattern": r"\d{1,3}",
                    "inputmode": "numeric",
                }
            ),
            "punto_emision": forms.TextInput(
                attrs={
                    "class": "form-control text-right",
                    "maxlength": "3",
                    "pattern": r"\d{1,3}",
                    "inputmode": "numeric",
                }
            ),
            "secuencia": forms.TextInput(
                attrs={
                    "class": "form-control text-right",
                    "maxlength": "9",
                    "pattern": r"\d{1,9}",
                    "inputmode": "numeric",
                }
            ),
            "tipo_liquidacion": forms.Select(attrs={"class": "form-control"}),
            "concepto": forms.TextInput(attrs={"class": "form-control"}),
            "autorizacion": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Ingrese el código de autorización"),
                }
            ),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "sustento_tributario": forms.Select(attrs={"class": "form-control"}),
        }

        labels = {
            "almacen": _("Almacén"),
            "establecimiento": _("Establecimiento (003)"),
            "punto_emision": _("Punto de emisión (003)"),
            "secuencia": _("Secuencial (000000001)"),
            "tipo_liquidacion": _("Liquidación"),
            "autorizacion": _("Autorización"),
            "sustento_tributario": _("Sustento tributario"),
        }

    def __init__(self, *args, empresa=None, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)

        if "tipo_liquidacion" in self.fields:
            self.fields["tipo_liquidacion"].choices = LiquidacionCompra.TIPO_LIQUIDACION_CHOICES
            if not self.initial.get("tipo_liquidacion"):
                self.initial["tipo_liquidacion"] = LiquidacionCompra.TIPO_LIQUIDACION_CHOICES[0][0]

        # Configurar queryset de proveedores según empresa activa y ocultar campo base
        self.fields["proveedor"].required = False
        self.fields["proveedor"].widget = forms.HiddenInput()
        if empresa:
            self.fields["proveedor"].queryset = Proveedor.objects.filter(empresa=empresa)
        else:
            self.fields["proveedor"].queryset = Proveedor.objects.none()

        if empresa:
            almacen_qs = Almacen.objects.filter(empresa=empresa, activo=True).order_by("descripcion")
            if self.instance and getattr(self.instance, "almacen_id", None):
                almacen_qs = Almacen.objects.filter(
                    Q(empresa=empresa, activo=True) | Q(pk=self.instance.almacen_id)
                ).order_by("descripcion")
            self.fields["almacen"].queryset = almacen_qs
        else:
            self.fields["almacen"].queryset = Almacen.objects.none()
        self.fields["almacen"].empty_label = _("Seleccione un almacén")

        proveedor = None
        if self.instance and getattr(self.instance, "proveedor", None):
            proveedor = self.instance.proveedor
        elif self.initial.get("proveedor"):
            try:
                proveedor = self.fields["proveedor"].queryset.get(pk=self.initial["proveedor"])
            except (Proveedor.DoesNotExist, TypeError, ValueError):
                proveedor = None

        if proveedor:
            self.initial.setdefault("beneficiario_tipo_identificacion", proveedor.tipoIdentificacion)
            self.initial.setdefault("beneficiario_identificacion", proveedor.identificacion_proveedor)
            self.initial.setdefault("beneficiario_nombre", proveedor.razon_social_proveedor)
            self.initial.setdefault("beneficiario_direccion", proveedor.direccion)
            self.initial.setdefault("beneficiario_correo", proveedor.correo)
            self.initial.setdefault("beneficiario_telefono", proveedor.telefono or proveedor.telefono2)
            self.initial.setdefault("proveedor", proveedor.pk)

        self.initial.setdefault("retencion_iva_porcentaje", Decimal("1.0000"))
        self.initial.setdefault("retencion_renta_porcentaje", Decimal("0.0000"))

        # Bloquear edición manual de los campos de secuencia cuando se autogeneran
        for campo in ("establecimiento", "punto_emision", "secuencia"):
            if campo in self.fields:
                widget = self.fields[campo].widget
                clases_actuales = widget.attrs.get("class", "").strip()
                widget.attrs["class"] = f"{clases_actuales} bg-gray-100".strip()
                widget.attrs["readonly"] = "readonly"
                widget.attrs["tabindex"] = "-1"

        # Formatear valores iniciales con ceros a la izquierda cuando estén presentes
        formatos = {"establecimiento": 3, "punto_emision": 3, "secuencia": 9}
        for campo, longitud in formatos.items():
            valor = self.initial.get(campo)
            if valor not in (None, ""):
                try:
                    self.initial[campo] = f"{int(valor):0{longitud}d}"
                except (TypeError, ValueError):
                    pass

    def clean(self):
        cleaned_data = super().clean()

        tipo_id = cleaned_data.get("beneficiario_tipo_identificacion")
        identificacion = cleaned_data.get("beneficiario_identificacion", "").strip()
        nombre = cleaned_data.get("beneficiario_nombre", "").strip()
        direccion = cleaned_data.get("beneficiario_direccion", "").strip()
        correo = cleaned_data.get("beneficiario_correo", "").strip()
        telefono = cleaned_data.get("beneficiario_telefono", "").strip()

        if not tipo_id:
            self.add_error("beneficiario_tipo_identificacion", _("Seleccione el tipo de identificación."))
        if not identificacion:
            self.add_error("beneficiario_identificacion", _("Ingrese la identificación del liquidado."))
        if not nombre:
            self.add_error("beneficiario_nombre", _("Ingrese el nombre del liquidado."))

        if self.errors:
            return cleaned_data

        if tipo_id == "04":
            self.add_error(
                "beneficiario_identificacion",
                _("Para Liquidación de Compra no corresponde RUC. Debe ingresar cédula (10 dígitos); si tiene RUC solicite Factura."),
            )

        if identificacion.isdigit() and len(identificacion) == 13:
            self.add_error(
                "beneficiario_identificacion",
                _("La identificación ingresada es RUC (13 dígitos). Para este caso corresponde Factura, no Liquidación de Compra."),
            )

        if not identificacion.isdigit() or len(identificacion) != 10:
            self.add_error(
                "beneficiario_identificacion",
                _("Para Liquidación de Compra debe ingresar una cédula válida de 10 dígitos."),
            )

        if self.errors:
            return cleaned_data

        # Campo oculto: normalizar a cédula cuando la identificación ya es válida de 10 dígitos.
        if identificacion.isdigit() and len(identificacion) == 10:
            tipo_id = "05"
            cleaned_data["beneficiario_tipo_identificacion"] = "05"

        if not self.empresa:
            raise forms.ValidationError(_("No se pudo determinar la empresa activa para la liquidación."))

        direccion_normalizada = direccion or str(_("SIN DIRECCIÓN REGISTRADA"))
        correo_final = correo or f"sin-correo-{identificacion}@liquidacion.local"

        proveedor_defaults = {
            "tipoIdentificacion": tipo_id,
            "razon_social_proveedor": nombre,
            "nombre_comercial_proveedor": nombre,
            "direccion": direccion_normalizada,
            "telefono": telefono,
            "telefono2": "",
            "correo": correo_final,
            "correo2": "",
            "observaciones": str(_("Generado desde liquidación de compra")),
            "convencional": "",
            "nacimiento": None,
            "tipoVenta": "1",
            "tipoRegimen": "1",
            "tipoProveedor": "1" if tipo_id != "04" else "2",
        }

        proveedor, _created = Proveedor.objects.update_or_create(
            empresa=self.empresa,
            identificacion_proveedor=identificacion,
            defaults=proveedor_defaults,
        )

        cleaned_data["proveedor"] = proveedor
        self.cleaned_data["proveedor"] = proveedor
        return cleaned_data

    def _valor_texto(self, campo: str) -> str:
        if not hasattr(self, "cleaned_data"):
            return ""
        valor = self.cleaned_data.get(campo, "")
        if isinstance(valor, str):
            return valor.strip()
        return valor or ""

    def get_prestador_data(self, liquidacion=None) -> dict:
        """Obtiene los datos normalizados del prestador asociados al formulario."""

        proveedor = getattr(liquidacion, "proveedor", None)

        data = {
            "tipo_identificacion": self._valor_texto("beneficiario_tipo_identificacion"),
            "identificacion": self._valor_texto("beneficiario_identificacion"),
            "nombre": self._valor_texto("beneficiario_nombre"),
            "direccion": self._valor_texto("beneficiario_direccion"),
            "correo": self._valor_texto("beneficiario_correo"),
            "telefono": self._valor_texto("beneficiario_telefono"),
        }

        if proveedor:
            data.setdefault("nombre_comercial", proveedor.nombre_comercial_proveedor or "")
            tipo_regimen = getattr(proveedor, "tipoRegimen", "") or ""
            data.setdefault("tipo_regimen", tipo_regimen)
            if not data.get("tipo_identificacion"):
                data["tipo_identificacion"] = proveedor.tipoIdentificacion or ""
            if not data.get("identificacion"):
                data["identificacion"] = proveedor.identificacion_proveedor or ""
            if not data.get("nombre"):
                data["nombre"] = proveedor.razon_social_proveedor or ""
        else:
            data.setdefault("nombre_comercial", "")
            data.setdefault("tipo_regimen", "")

        return data

    def guardar_prestador(self, liquidacion):
        """Crea o actualiza el prestador ligado a la liquidación."""

        if not hasattr(self, "cleaned_data"):
            raise ValueError("El formulario debe validarse antes de guardar el prestador.")

        from .models import Prestador

        datos = self.get_prestador_data(liquidacion=liquidacion)
        datos.setdefault("obligado_contabilidad", "NO")
        datos.setdefault("tipo_contribuyente", "")
        datos.setdefault("actividad_economica", "")
        datos.setdefault("estado", "")
        datos["proveedor"] = getattr(liquidacion, "proveedor", None)
        datos["empresa"] = getattr(liquidacion, "empresa", None)

        if not datos.get("tipo_identificacion") or not datos.get("identificacion") or not datos.get("nombre"):
            raise ValueError("Los datos del prestador son incompletos.")
        if datos.get("empresa") is None:
            raise ValueError("La liquidación debe estar asociada a una empresa para guardar al prestador.")

        prestador, _ = Prestador.objects.update_or_create(
            liquidacion=liquidacion,
            defaults=datos,
        )
        return prestador


class LiquidacionDetalleForm(forms.ModelForm):
    # Sobrescribir producto y servicio como IntegerField para evitar validación de ModelChoiceField
    # El JavaScript envía IDs pero no queremos validar contra queryset aquí
    producto = forms.IntegerField(required=False, widget=forms.HiddenInput())
    servicio = forms.IntegerField(required=False, widget=forms.HiddenInput())
    
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
            "codigo_iva",
            "tarifa_iva",
            "valor_iva",
            "valor_ice",
            "valor_irbp",
            "precio_unitario_con_impuestos",
            "total_con_impuestos",
        ]
        widgets = {
            "descripcion": forms.TextInput(attrs={"class": "form-control"}),
            "unidad_medida": forms.TextInput(attrs={"class": "form-control"}),
            "cantidad": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "costo": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "descuento": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "codigo_iva": forms.HiddenInput(),
            "tarifa_iva": forms.HiddenInput(),
            "valor_iva": forms.HiddenInput(),
            "valor_ice": forms.HiddenInput(),
            "valor_irbp": forms.HiddenInput(),
            "precio_unitario_con_impuestos": forms.HiddenInput(),
            "total_con_impuestos": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Los campos producto y servicio ya están definidos como IntegerField arriba

    def clean(self):
        cleaned = super().clean()
        
        # Convertir IDs de producto/servicio a instancias reales
        from ..models import Producto, Servicio
        
        producto_id = cleaned.get("producto")
        servicio_id = cleaned.get("servicio")
        
        producto = None
        servicio = None
        
        if producto_id:
            try:
                producto = Producto.objects.get(pk=producto_id)
                cleaned["producto"] = producto
            except Producto.DoesNotExist:
                # Si el producto no existe, lo dejamos como None
                cleaned["producto"] = None
                
        if servicio_id:
            try:
                servicio = Servicio.objects.get(pk=servicio_id)
                cleaned["servicio"] = servicio
            except Servicio.DoesNotExist:
                # Si el servicio no existe, lo dejamos como None
                cleaned["servicio"] = None
        
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

        cleaned["codigo_iva"] = (cleaned.get("codigo_iva") or "").strip() or "0"

        for campo in ("tarifa_iva", "valor_iva", "valor_ice", "valor_irbp", "precio_unitario_con_impuestos", "total_con_impuestos"):
            valor = cleaned.get(campo)
            if valor in (None, ""):
                cleaned[campo] = Decimal("0")
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
