"""Formularios para la emisión de Liquidaciones de Compra."""
from __future__ import annotations

from django import forms
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
        max_length=13,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "maxlength": "13",
                "placeholder": _("Ingrese identificación"),
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
        ]
        widgets = {
            "proveedor": forms.HiddenInput(),
            "almacen": forms.Select(attrs={"class": "form-control"}),
            "establecimiento": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 999}),
            "punto_emision": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 999}),
            "secuencia": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 999999999}),
            "concepto": forms.TextInput(attrs={"class": "form-control"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "sustento_tributario": forms.Select(attrs={"class": "form-control"}),
        }

        labels = {
            "almacen": _("Almacén"),
            "establecimiento": _("Establecimiento (003)"),
            "punto_emision": _("Punto de emisión (003)"),
            "secuencia": _("Secuencial (000000001)"),
            "sustento_tributario": _("Sustento tributario"),
        }

    def __init__(self, *args, empresa=None, **kwargs):
        self.empresa = empresa
        super().__init__(*args, **kwargs)

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

        if tipo_id == "05" and len(identificacion) not in (10, 13):
            self.add_error("beneficiario_identificacion", _("La cédula debe tener 10 o 13 dígitos."))
        if tipo_id == "04" and len(identificacion) != 13:
            self.add_error("beneficiario_identificacion", _("El RUC debe tener 13 dígitos."))

        if self.errors:
            return cleaned_data

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
