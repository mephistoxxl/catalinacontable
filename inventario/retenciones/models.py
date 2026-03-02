from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from ..tenant.queryset import TenantManager


class ComprobanteRetencion(models.Model):
    ESTADOS_SRI = [
        ("", "No enviada"),
        ("PENDIENTE", "Pendiente"),
        ("RECIBIDA", "Recibida"),
        ("AUTORIZADA", "Autorizada"),
        ("RECHAZADA", "Rechazada"),
        ("ERROR", "Error"),
    ]

    TIPO_DOCUMENTO_SUSTENTO = [
        ("01", "(01) Factura"),
        ("03", "(03) Liquidación de Compra"),
    ]

    TIPO_RETENCION = [
        ("001901", "Retención Electrónica 001 901"),
    ]

    empresa = models.ForeignKey(
        "inventario.Empresa",
        on_delete=models.CASCADE,
        related_name="retenciones_emitidas",
    )
    usuario_creacion = models.ForeignKey(
        "inventario.Usuario",
        on_delete=models.PROTECT,
        related_name="retenciones_creadas",
    )
    proveedor = models.ForeignKey(
        "inventario.Proveedor",
        on_delete=models.PROTECT,
        related_name="retenciones",
        null=True,
        blank=True,
    )

    fecha_emision = models.DateField(default=timezone.localdate)
    identificacion_sujeto = models.CharField(max_length=20, blank=True, default="")
    razon_social_sujeto = models.CharField(max_length=300, blank=True, default="")

    tipo_documento_sustento = models.CharField(
        max_length=2,
        choices=TIPO_DOCUMENTO_SUSTENTO,
        default="01",
    )
    establecimiento_doc = models.CharField(
        max_length=3,
        default="001",
        validators=[RegexValidator(r"^\d{3}$", "Debe tener 3 dígitos.")],
    )
    punto_emision_doc = models.CharField(
        max_length=3,
        default="001",
        validators=[RegexValidator(r"^\d{3}$", "Debe tener 3 dígitos.")],
    )
    secuencia_doc = models.CharField(
        max_length=9,
        default="000000001",
        validators=[RegexValidator(r"^\d{9}$", "Debe tener 9 dígitos.")],
    )
    autorizacion_doc_sustento = models.CharField(max_length=49, blank=True, default="")

    forma_pago_sri = models.CharField(max_length=5, blank=True, default="20")
    sustento_tributario = models.CharField(max_length=5, blank=True, default="00")
    forma_pago = models.CharField(max_length=20, blank=True, default="EFECTIVO")

    base_iva_0 = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    base_iva_5 = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    base_no_obj_iva = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    base_exento_iva = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    base_iva = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    monto_iva = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    porcentaje_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    monto_ice = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    tipo_retencion = models.CharField(max_length=6, choices=TIPO_RETENCION, default="001901")
    fecha_emision_retencion = models.DateField(default=timezone.localdate)
    establecimiento_retencion = models.CharField(
        max_length=3,
        default="001",
        validators=[RegexValidator(r"^\d{3}$", "Debe tener 3 dígitos.")],
    )
    punto_emision_retencion = models.CharField(
        max_length=3,
        default="901",
        validators=[RegexValidator(r"^\d{3}$", "Debe tener 3 dígitos.")],
    )
    secuencia_retencion = models.CharField(
        max_length=9,
        validators=[RegexValidator(r"^\d{9}$", "Debe tener 9 dígitos.")],
    )
    autorizacion_retencion = models.CharField(max_length=49, blank=True, default="")

    total_retencion_renta = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_retencion_iva = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_retenido = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    estado_sri = models.CharField(max_length=15, choices=ESTADOS_SRI, default="")
    numero_autorizacion = models.CharField(max_length=49, blank=True, default="")
    clave_acceso = models.CharField(max_length=49, blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    _unsafe_objects = models.Manager()

    class Meta:
        indexes = [
            models.Index(fields=["empresa", "fecha_emision_retencion"]),
            models.Index(fields=["empresa", "estado_sri"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "establecimiento_retencion", "punto_emision_retencion", "secuencia_retencion"],
                name="uniq_retencion_empresa_serie_sec",
            )
        ]
        ordering = ("-fecha_emision_retencion", "-id")

    def __str__(self) -> str:
        return f"Retención {self.numero_completo}"

    @property
    def numero_completo(self) -> str:
        return f"{self.establecimiento_retencion}-{self.punto_emision_retencion}-{self.secuencia_retencion}"

    def recalcular_totales(self) -> None:
        agregados = self.detalles.aggregate(
            renta=Sum("valor_retenido", filter=models.Q(tipo_impuesto="RENTA")),
            iva=Sum("valor_retenido", filter=models.Q(tipo_impuesto="IVA")),
        )
        self.total_retencion_renta = (agregados.get("renta") or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.total_retencion_iva = (agregados.get("iva") or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.total_retenido = (self.total_retencion_renta + self.total_retencion_iva).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class RetencionDetalle(models.Model):
    TIPO_IMPUESTO_CHOICES = [
        ("RENTA", "Renta"),
        ("IVA", "IVA"),
    ]

    comprobante = models.ForeignKey(
        ComprobanteRetencion,
        on_delete=models.CASCADE,
        related_name="detalles",
    )
    tipo_impuesto = models.CharField(max_length=10, choices=TIPO_IMPUESTO_CHOICES)
    codigo_retencion = models.CharField(max_length=10)
    descripcion_retencion = models.CharField(max_length=255, blank=True, default="")
    base_imponible = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    porcentaje_retener = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    valor_retenido = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["tipo_impuesto", "codigo_retencion"])]
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.tipo_impuesto} {self.codigo_retencion} - {self.valor_retenido}"
