from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from random import randint

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from ..tenant.queryset import TenantManager


CODIGO_IMPUESTO_CHOICES = (
    ("1", "Renta"),
    ("2", "IVA"),
    ("6", "ISD"),
    ("4", "IVA Presuntivo/Renta"),
)

TIPO_IDENTIFICACION_SUJETO_CHOICES = (
    ("04", "RUC"),
    ("05", "Cédula"),
    ("06", "Pasaporte"),
    ("08", "Identificación del exterior"),
)

COD_DOC_SUSTENTO_CHOICES = (
    ("01", "Factura"),
    ("03", "Liquidación de Compra"),
    ("04", "Nota de Crédito"),
)


class RetencionCompra(models.Model):
    ESTADOS_INTERNOS = (
        ("BORRADOR", "Borrador"),
        ("LISTA", "Lista"),
        ("FIRMADA", "Firmada"),
        ("ENVIADA", "Enviada"),
        ("AUTORIZADA", "Autorizada"),
        ("RECHAZADA", "Rechazada"),
        ("ANULADA", "Anulada"),
    )

    ESTADOS_SRI = (
        ("", "No enviada"),
        ("PENDIENTE", "Pendiente"),
        ("RECIBIDA", "Recibida"),
        ("AUTORIZADO", "Autorizado"),
        ("NO AUTORIZADO", "No autorizado"),
        ("RECHAZADA", "Rechazada"),
        ("ERROR", "Error"),
    )

    VERSION_XML_CHOICES = (
        ("1.0.0", "Versión 1.0.0"),
        ("2.0.0", "Versión 2.0.0 ATS"),
    )

    empresa = models.ForeignKey(
        "inventario.Empresa",
        on_delete=models.CASCADE,
        related_name="retenciones_compra",
    )
    proveedor = models.ForeignKey(
        "inventario.Proveedor",
        on_delete=models.PROTECT,
        related_name="retenciones_compra",
    )
    usuario_creacion = models.ForeignKey(
        "inventario.Usuario",
        on_delete=models.PROTECT,
        related_name="retenciones_emitidas",
    )

    fecha_emision = models.DateField(default=timezone.localdate)
    fecha_emision_doc_sustento = models.DateField(default=timezone.localdate)

    establecimiento = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(999)])
    punto_emision = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(999)])
    secuencia = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(999999999)])

    version_xml = models.CharField(max_length=5, choices=VERSION_XML_CHOICES, default="2.0.0")
    cod_doc_sustento = models.CharField(max_length=2, choices=COD_DOC_SUSTENTO_CHOICES, default="01")
    num_doc_sustento = models.CharField(max_length=15)
    num_aut_doc_sustento = models.CharField(max_length=49, blank=True, null=True)

    tipo_identificacion_sujeto_retenido = models.CharField(max_length=2, choices=TIPO_IDENTIFICACION_SUJETO_CHOICES)
    razon_social_sujeto_retenido = models.CharField(max_length=300)
    identificacion_sujeto_retenido = models.CharField(max_length=13)

    periodo_fiscal = models.CharField(max_length=7, blank=True)

    total_sin_impuestos_doc = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_iva_doc = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    importe_total_doc = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    total_retenido_renta = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_retenido_iva = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_retenido = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    codigo_interno = models.CharField(max_length=8, blank=True, default="")
    clave_acceso = models.CharField(max_length=49, blank=True, null=True, unique=True)

    estado = models.CharField(max_length=15, choices=ESTADOS_INTERNOS, default="BORRADOR")
    estado_sri = models.CharField(max_length=20, choices=ESTADOS_SRI, default="")
    mensaje_sri = models.TextField(blank=True, null=True)

    numero_autorizacion = models.CharField(max_length=49, blank=True, null=True)
    fecha_autorizacion = models.DateTimeField(blank=True, null=True)

    xml_generado = models.TextField(blank=True, null=True)
    xml_firmado = models.TextField(blank=True, null=True)
    xml_autorizado = models.TextField(blank=True, null=True)

    observaciones = models.TextField(blank=True, null=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    _unsafe_objects = models.Manager()

    class Meta:
        ordering = ("-fecha_emision", "-id")
        indexes = [
            models.Index(fields=["empresa", "fecha_emision"]),
            models.Index(fields=["empresa", "estado"]),
            models.Index(fields=["empresa", "estado_sri"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "establecimiento", "punto_emision", "secuencia"],
                name="uniq_retencion_empresa_serie_sec",
            )
        ]

    def __str__(self) -> str:
        return f"Retención {self.serie_formateada}-{self.secuencia_formateada}"

    @staticmethod
    def _money(value: Decimal | float | int | str) -> Decimal:
        return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def serie_formateada(self) -> str:
        return f"{int(self.establecimiento):03d}-{int(self.punto_emision):03d}"

    @property
    def secuencia_formateada(self) -> str:
        return f"{int(self.secuencia):09d}"

    def calcular_totales(self) -> None:
        total_renta = Decimal("0.00")
        total_iva = Decimal("0.00")
        total_general = Decimal("0.00")

        for impuesto in self.impuestos.all():
            valor = self._money(impuesto.valor_retenido)
            total_general += valor
            if impuesto.codigo == "1":
                total_renta += valor
            elif impuesto.codigo == "2":
                total_iva += valor

        self.total_retenido_renta = self._money(total_renta)
        self.total_retenido_iva = self._money(total_iva)
        self.total_retenido = self._money(total_general)

    def clean(self):
        super().clean()
        if not self.periodo_fiscal and self.fecha_emision:
            self.periodo_fiscal = self.fecha_emision.strftime("%m/%Y")

    def save(self, *args, **kwargs):
        if not self.periodo_fiscal and self.fecha_emision:
            self.periodo_fiscal = self.fecha_emision.strftime("%m/%Y")
        super().save(*args, **kwargs)

    def generar_clave_acceso(self, codigo_numerico: str | None = None) -> str:
        fecha = self.fecha_emision.strftime("%d%m%Y")
        cod_doc = "07"

        opciones = self.empresa.opciones.first() if hasattr(self.empresa, "opciones") else None
        ruc = "0000000000000"
        if opciones and opciones.identificacion:
            ruc = str(opciones.identificacion).zfill(13)

        ambiente = "1"
        if opciones and str(opciones.tipo_ambiente) in {"1", "2"}:
            ambiente = str(opciones.tipo_ambiente)

        serie = f"{int(self.establecimiento):03d}{int(self.punto_emision):03d}"
        secuencial = f"{int(self.secuencia):09d}"

        codigo_base = codigo_numerico or self.codigo_interno or f"{randint(0, 99999999):08d}"
        codigo_base = str(codigo_base).zfill(8)[-8:]
        self.codigo_interno = codigo_base

        tipo_emision = "1"
        if opciones and str(opciones.tipo_emision) in {"1", "2"}:
            tipo_emision = str(opciones.tipo_emision)

        base = f"{fecha}{cod_doc}{ruc}{ambiente}{serie}{secuencial}{codigo_base}{tipo_emision}"

        suma = 0
        multiplicadores = [2, 3, 4, 5, 6, 7]
        for idx, digito in enumerate(reversed(base)):
            suma += int(digito) * multiplicadores[idx % len(multiplicadores)]

        residuo = suma % 11
        verificador = 11 - residuo
        if verificador == 11:
            verificador = 0
        elif verificador == 10:
            verificador = 1

        clave = f"{base}{verificador}"
        self.clave_acceso = clave
        return clave


class RetencionImpuesto(models.Model):
    retencion = models.ForeignKey(
        RetencionCompra,
        on_delete=models.CASCADE,
        related_name="impuestos",
    )
    codigo = models.CharField(max_length=1, choices=CODIGO_IMPUESTO_CHOICES)
    codigo_retencion = models.CharField(max_length=10)
    base_imponible = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    porcentaje_retener = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.0000"))
    valor_retenido = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "Impuesto Retenido"
        verbose_name_plural = "Impuestos Retenidos"

    @staticmethod
    def _money(value: Decimal | float | int | str) -> Decimal:
        return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calcular_valor_retenido(self) -> Decimal:
        valor = Decimal(self.base_imponible or 0) * (Decimal(self.porcentaje_retener or 0) / Decimal("100"))
        return self._money(valor)

    def clean(self):
        super().clean()
        esperado = self.calcular_valor_retenido()
        if self.valor_retenido in (None, ""):
            self.valor_retenido = esperado
            return
        valor_actual = self._money(self.valor_retenido)
        if valor_actual != esperado:
            raise ValidationError(
                {
                    "valor_retenido": (
                        f"El valor retenido debe ser {esperado} según base*porcentaje/100 "
                        "(regla SRI de diferencias)."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.valor_retenido = self.calcular_valor_retenido()
        super().save(*args, **kwargs)


class RetencionCampoAdicional(models.Model):
    retencion = models.ForeignKey(
        RetencionCompra,
        on_delete=models.CASCADE,
        related_name="campos_adicionales",
    )
    nombre = models.CharField(max_length=300)
    valor = models.CharField(max_length=300)

    class Meta:
        verbose_name = "Campo adicional de retención"
        verbose_name_plural = "Campos adicionales de retención"


class RetencionLogCambioEstado(models.Model):
    retencion = models.ForeignKey(
        RetencionCompra,
        on_delete=models.CASCADE,
        related_name="historial_estados",
    )
    estado = models.CharField(max_length=15, choices=RetencionCompra.ESTADOS_INTERNOS)
    estado_sri = models.CharField(max_length=20, blank=True)
    mensaje = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-creado_en",)
        verbose_name = "Historial de retención"
        verbose_name_plural = "Historial de retenciones"
