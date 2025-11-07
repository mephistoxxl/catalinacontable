"""Modelos dedicados a la emisión de Liquidaciones de Compra (codDoc 03).
Se definen en un submódulo para mantener aislada la facturación existente.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

from ..tenant.queryset import TenantManager


class LiquidacionCompra(models.Model):
    """Representa la cabecera de una Liquidación de Compra electrónica."""

    ESTADOS_INTERNOS = [
        ("BORRADOR", "Borrador"),
        ("LISTA", "Lista para firma"),
        ("FIRMADA", "Firmada"),
        ("ENVIADA", "Enviada al SRI"),
        ("AUTORIZADA", "Autorizada"),
        ("RECHAZADA", "Rechazada"),
        ("ANULADA", "Anulada"),
    ]

    ESTADOS_SRI = [
        ("", "No enviada"),
        ("PENDIENTE", "Pendiente"),
        ("RECIBIDA", "Recibida"),
        ("AUTORIZADA", "Autorizada"),
        ("RECHAZADA", "Rechazada"),
        ("ERROR", "Error"),
    ]

    SUSTENTOS_TRIBUTARIOS = [
        ("01", "Crédito tributario para declaraciones"),
        ("02", "Gasto personal"),
        ("03", "Activo fijo"),
        ("04", "Gasto general"),
        ("05", "Inventarios"),
        ("06", "Exportaciones"),
        ("07", "Otros"),
    ]

    TIPO_LIQUIDACION_CHOICES = [
        ("001901", "001901 Liquidación de Compra Electrónica"),
    ]

    MONEDAS = [
        ("DOLAR", "Dólar (USD)"),
        ("EUR", "Euro"),
    ]

    empresa = models.ForeignKey(
        "inventario.Empresa",
        on_delete=models.CASCADE,
        related_name="liquidaciones_compra",
    )
    proveedor = models.ForeignKey(
        "inventario.Proveedor",
        on_delete=models.PROTECT,
        related_name="liquidaciones_compra",
    )
    almacen = models.ForeignKey(
        "inventario.Almacen",
        on_delete=models.PROTECT,
        related_name="liquidaciones_compra",
        null=True,
        blank=True,
    )
    usuario_creacion = models.ForeignKey(
        "inventario.Usuario",
        on_delete=models.PROTECT,
        related_name="liquidaciones_emitidas",
    )

    fecha_emision = models.DateField(default=timezone.now)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    establecimiento = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(999)],
    )
    punto_emision = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(999)],
    )
    secuencia = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(999_999_999)],
    )

    tipo_liquidacion = models.CharField(
        max_length=6,
        choices=TIPO_LIQUIDACION_CHOICES,
        default="001901",
    )
    concepto = models.CharField(max_length=255, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    autorizacion = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9A-Za-z\s\-]+$",
                message="La autorización solo puede contener letras, números, espacios o guiones.",
            )
        ],
    )
    sustento_tributario = models.CharField(
        max_length=2,
        choices=SUSTENTOS_TRIBUTARIOS,
        default="01",
    )

    total_sin_impuestos = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_descuento = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_con_impuestos = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    importe_total = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    propina = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    moneda = models.CharField(max_length=10, choices=MONEDAS, default="DOLAR")

    base_imponible_gravada = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    base_imponible_reducida = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    base_imponible_cero = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    base_no_objeto = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    base_exenta = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    valor_total_iva = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    valor_total_ice = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    valor_total_irbp = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    iva_presuntivo = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    retencion_iva_porcentaje = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("1.0000"))
    retencion_renta_porcentaje = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0.0000"))
    retencion_iva = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    retencion_renta = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    total_items = models.PositiveIntegerField(default=0)
    total_cantidad = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0.000000"))

    clave_acceso = models.CharField(max_length=49, blank=True, null=True, unique=True)
    numero_autorizacion = models.CharField(max_length=49, blank=True, null=True)
    fecha_autorizacion = models.DateTimeField(blank=True, null=True)

    estado = models.CharField(max_length=15, choices=ESTADOS_INTERNOS, default="BORRADOR")
    estado_sri = models.CharField(max_length=15, choices=ESTADOS_SRI, default="")
    mensaje_sri = models.TextField(blank=True, null=True)
    xml_firmado = models.TextField(blank=True, null=True)
    xml_autorizado = models.TextField(blank=True, null=True)

    # Auditoría
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    # ⚠️ Uso exclusivo para migraciones/tests: evita filtros multi-tenant automáticos.
    _unsafe_objects = models.Manager()

    class Meta:
        indexes = [
            models.Index(fields=["empresa", "fecha_emision"]),
            models.Index(fields=["empresa", "estado"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "establecimiento", "punto_emision", "secuencia"],
                name="uniq_liquidacion_empresa_serie_sec",
            )
        ]
        ordering = ("-fecha_emision", "-id")

    def __str__(self) -> str:  # pragma: no cover - representación simple
        return f"Liquidación {self.serie_formateada}-{self.secuencia_formateada}"

    # -----------------------------
    # Propiedades formateadas SRI
    # -----------------------------
    @property
    def serie_formateada(self) -> str:
        return f"{int(self.establecimiento):03d}-{int(self.punto_emision):03d}"

    @property
    def secuencia_formateada(self) -> str:
        return f"{int(self.secuencia):09d}"

    # -----------------------------
    # Reglas de negocio críticas
    # -----------------------------
    def calcular_totales(self) -> None:
        """Recalcula totales y campos derivados en memoria."""
        subtotal_bruto = Decimal("0.00")
        descuento = Decimal("0.00")

        self.iva_presuntivo = Decimal("0.00")

        base_gravada = Decimal("0.00")
        base_reducida = Decimal("0.00")
        base_cero = Decimal("0.00")
        base_no_obj = Decimal("0.00")
        base_exenta = Decimal("0.00")

        total_iva = Decimal("0.00")
        total_ice = Decimal("0.00")
        total_irbp = Decimal("0.00")

        total_cantidad = Decimal("0.000000")
        total_items = 0

        detalles_qs = self.detalles.all().select_related("producto", "servicio")
        for detalle in detalles_qs:
            subtotal_detalle = (detalle.costo * detalle.cantidad).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            subtotal_bruto += subtotal_detalle
            descuento += detalle.descuento

            base_imponible = detalle.precio_total_sin_impuesto
            codigo_iva = (detalle.codigo_iva or "").strip()

            if codigo_iva == "0":
                base_cero += base_imponible
            elif codigo_iva == "5":
                base_reducida += base_imponible
            elif codigo_iva == "6":
                base_no_obj += base_imponible
            elif codigo_iva == "7":
                base_exenta += base_imponible
            else:
                base_gravada += base_imponible

            total_iva += detalle.valor_iva
            total_ice += detalle.valor_ice
            total_irbp += detalle.valor_irbp
            total_cantidad += detalle.cantidad
            total_items += 1

        self.base_imponible_gravada = base_gravada.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.base_imponible_reducida = base_reducida.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.base_imponible_cero = base_cero.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.base_no_objeto = base_no_obj.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.base_exenta = base_exenta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        subtotal_neto = self.base_imponible_gravada + self.base_imponible_reducida + self.base_imponible_cero + self.base_no_objeto + self.base_exenta
        self.total_sin_impuestos = subtotal_neto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.total_descuento = descuento.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        self.valor_total_iva = total_iva.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.valor_total_ice = total_ice.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.valor_total_irbp = total_irbp.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        total_con_impuestos = self.total_sin_impuestos + self.valor_total_iva + self.valor_total_ice + self.valor_total_irbp
        self.total_con_impuestos = total_con_impuestos.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.importe_total = (self.total_con_impuestos + self.propina).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        ret_iva = self.valor_total_iva * (self.retencion_iva_porcentaje or Decimal("0"))
        ret_renta = self.total_sin_impuestos * (self.retencion_renta_porcentaje or Decimal("0"))
        self.retencion_iva = ret_iva.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.retencion_renta = ret_renta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        self.total_items = total_items
        self.total_cantidad = total_cantidad.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    def sincronizar_formas_pago(self) -> None:
        """Ajusta automáticamente la forma de pago principal si hay desviaciones."""
        from decimal import Decimal as Dec

        total_pagos = sum((p.total for p in self.formas_pago.all()), Dec("0.00"))
        diferencia = (self.importe_total - total_pagos).quantize(Dec("0.01"), rounding=ROUND_HALF_UP)
        if not self.formas_pago.exists() and self.importe_total > Dec("0.00"):
            self.formas_pago.create(forma_pago="01", total=self.importe_total)
        elif diferencia != Dec("0.00") and self.formas_pago.exists():
            principal = self.formas_pago.order_by("-total").first()
            if principal:
                principal.total = (principal.total + diferencia).quantize(Dec("0.01"), rounding=ROUND_HALF_UP)
                principal.save(update_fields=["total"])

    def generar_clave_acceso(self, codigo_numerico: str | None = None) -> str:
        """Genera la clave de acceso codDoc 03 siguiendo módulo 11."""
        from random import randint

        fecha = self.fecha_emision.strftime("%d%m%Y")
        cod_doc = "03"
        opciones = self.empresa.opciones.first() if hasattr(self.empresa, "opciones") else None
        ruc = opciones.identificacion.zfill(13) if opciones and opciones.identificacion else "0000000000000"
        ambiente = opciones.tipo_ambiente if opciones and opciones.tipo_ambiente in {"1", "2"} else "1"
        serie = f"{int(self.establecimiento):03d}{int(self.punto_emision):03d}"
        secuencial = f"{int(self.secuencia):09d}"
        cod_num = codigo_numerico or f"{randint(0, 99999999):08d}"
        tipo_emision = opciones.tipo_emision if opciones and opciones.tipo_emision in {"1", "2"} else "1"

        base = f"{fecha}{cod_doc}{ruc}{ambiente}{serie}{secuencial}{cod_num}{tipo_emision}"
        acumulado = 0
        multiplicadores = [2, 3, 4, 5, 6, 7]
        for i, digito in enumerate(reversed(base)):
            acumulado += int(digito) * multiplicadores[i % len(multiplicadores)]
        residuo = acumulado % 11
        digito_verificador = 11 - residuo
        if digito_verificador == 11:
            digito_verificador = 0
        elif digito_verificador == 10:
            digito_verificador = 1

        clave = f"{base}{digito_verificador}"
        self.clave_acceso = clave
        return clave


IVA_CODE_PERCENT_MAP = {
    "0": Decimal("0.00"),
    "5": Decimal("0.05"),
    "2": Decimal("0.12"),
    "10": Decimal("0.13"),
    "3": Decimal("0.14"),
    "4": Decimal("0.15"),
    "9": Decimal("0.15"),
    "8": Decimal("0.08"),
    "6": Decimal("0.00"),
    "7": Decimal("0.00"),
}


class LiquidacionDetalle(models.Model):
    """Detalle de productos/servicios en la liquidación."""

    liquidacion = models.ForeignKey(
        LiquidacionCompra,
        on_delete=models.CASCADE,
        related_name="detalles",
    )
    producto = models.ForeignKey(
        "inventario.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    servicio = models.ForeignKey(
        "inventario.Servicio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    descripcion = models.CharField(max_length=300)
    unidad_medida = models.CharField(max_length=50, blank=True, null=True)
    cantidad = models.DecimalField(max_digits=20, decimal_places=6, validators=[MinValueValidator(Decimal("0.000001"))])
    costo = models.DecimalField(max_digits=20, decimal_places=6, validators=[MinValueValidator(Decimal("0.00"))])
    descuento = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    precio_total_sin_impuesto = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    codigo_iva = models.CharField(max_length=4, blank=True, default="2")
    tarifa_iva = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal("0.0000"))
    valor_iva = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    valor_ice = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    valor_irbp = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    precio_unitario_con_impuestos = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0.000000"))
    total_con_impuestos = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "Detalle de Liquidación"
        verbose_name_plural = "Detalles de Liquidación"

    def calcular_totales(self) -> None:
        subtotal = (self.costo * self.cantidad).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        base_imponible = (subtotal - self.descuento).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.precio_total_sin_impuesto = base_imponible

        tarifa_iva = self.tarifa_iva or Decimal("0.0000")
        codigo_iva = (self.codigo_iva or "").strip()

        if not codigo_iva and self.producto:
            codigo_iva = self.producto.iva
        if not codigo_iva and self.servicio:
            codigo_iva = getattr(self.servicio, "iva", "")

        if not tarifa_iva or tarifa_iva < Decimal("0"):
            tarifa_iva = Decimal("0.0000")
        if codigo_iva in IVA_CODE_PERCENT_MAP:
            tarifa_iva = IVA_CODE_PERCENT_MAP[codigo_iva]
        else:
            for codigo, porcentaje in IVA_CODE_PERCENT_MAP.items():
                if abs(porcentaje - tarifa_iva) < Decimal("0.0001"):
                    codigo_iva = codigo
                    break
            else:
                codigo_iva = "2" if tarifa_iva > Decimal("0") else "0"

        self.codigo_iva = codigo_iva
        self.tarifa_iva = tarifa_iva.quantize(Decimal("0.0001"))

        self.valor_ice = (self.valor_ice or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.valor_irbp = (self.valor_irbp or Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        self.valor_iva = (base_imponible * self.tarifa_iva).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.precio_unitario_con_impuestos = (
            self.costo * (Decimal("1.0000") + self.tarifa_iva)
        ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        total_impuestos = (self.valor_iva + self.valor_ice + self.valor_irbp).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.total_con_impuestos = (base_imponible + total_impuestos).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):  # pragma: no cover - lógica trivial
        self.calcular_totales()
        super().save(*args, **kwargs)


class LiquidacionDetalleImpuesto(models.Model):
    """Impuestos por línea."""

    detalle = models.ForeignKey(
        LiquidacionDetalle,
        on_delete=models.CASCADE,
        related_name="impuestos",
    )
    codigo = models.CharField(max_length=1)
    codigo_porcentaje = models.CharField(max_length=4)
    tarifa = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    base_imponible = models.DecimalField(max_digits=20, decimal_places=2)
    valor = models.DecimalField(max_digits=20, decimal_places=2)

    class Meta:
        verbose_name = "Impuesto de Detalle"
        verbose_name_plural = "Impuestos de Detalle"


class LiquidacionTotalImpuesto(models.Model):
    """Totales de impuestos por tarifa."""

    liquidacion = models.ForeignKey(
        LiquidacionCompra,
        on_delete=models.CASCADE,
        related_name="totales_impuestos",
    )
    codigo = models.CharField(max_length=1)
    codigo_porcentaje = models.CharField(max_length=4)
    base_imponible = models.DecimalField(max_digits=20, decimal_places=2)
    valor = models.DecimalField(max_digits=20, decimal_places=2)
    descuento_adicional = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "Total de Impuesto"
        verbose_name_plural = "Totales de Impuesto"


FORMAS_PAGO_SRI = (
    ("01", "Sin utilización del sistema financiero"),
    ("15", "Compensación de deudas"),
    ("16", "Tarjeta de débito"),
    ("17", "Dinero electrónico"),
    ("18", "Tarjeta prepago"),
    ("19", "Tarjeta de crédito"),
    ("20", "Otros con utilización del sistema financiero"),
    ("21", "Endoso de títulos"),
)


class LiquidacionFormaPago(models.Model):
    """Formas de pago específicas de una liquidación."""

    liquidacion = models.ForeignKey(
        LiquidacionCompra,
        on_delete=models.CASCADE,
        related_name="formas_pago",
    )
    forma_pago = models.CharField(max_length=2, choices=FORMAS_PAGO_SRI)
    total = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    plazo = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    unidad_tiempo = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        verbose_name = "Forma de Pago de Liquidación"
        verbose_name_plural = "Formas de Pago de Liquidación"
        unique_together = ("liquidacion", "forma_pago")


class Prestador(models.Model):
    """Titular del comprobante de liquidación de compra."""

    TIPO_IDENTIFICACION_CHOICES = (
        ("04", "RUC"),
        ("05", "Cédula"),
        ("06", "Pasaporte"),
        ("07", "Consumidor final"),
        ("08", "Identificación del exterior"),
    )

    OPCIONES_SI_NO = (("SI", "Sí"), ("NO", "No"))

    empresa = models.ForeignKey(
        "inventario.Empresa",
        on_delete=models.CASCADE,
        related_name="prestadores",
    )
    liquidacion = models.OneToOneField(
        LiquidacionCompra,
        on_delete=models.CASCADE,
        related_name="prestador",
    )
    proveedor = models.ForeignKey(
        "inventario.Proveedor",
        on_delete=models.PROTECT,
        related_name="prestadores",
        null=True,
        blank=True,
    )
    tipo_identificacion = models.CharField(max_length=2, choices=TIPO_IDENTIFICACION_CHOICES)
    identificacion = models.CharField(max_length=13)
    nombre = models.CharField(max_length=255)
    nombre_comercial = models.CharField(max_length=255, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    correo = models.EmailField(max_length=200, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    obligado_contabilidad = models.CharField(max_length=2, choices=OPCIONES_SI_NO, default="NO")
    tipo_contribuyente = models.CharField(max_length=150, blank=True)
    actividad_economica = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=120, blank=True)
    tipo_regimen = models.CharField(max_length=120, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    # ⚠️ Uso exclusivo para migraciones/tests: evita filtros multi-tenant automáticos.
    _unsafe_objects = models.Manager()

    class Meta:
        verbose_name = "Prestador"
        verbose_name_plural = "Prestadores"
        indexes = [
            models.Index(fields=["identificacion"]),
            models.Index(fields=["tipo_identificacion", "identificacion"]),
            models.Index(fields=["empresa", "identificacion"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - representación simple
        return f"Prestador {self.identificacion}"


class LiquidacionCampoAdicional(models.Model):
    """Campos adicionales opcionales."""

    liquidacion = models.ForeignKey(
        LiquidacionCompra,
        on_delete=models.CASCADE,
        related_name="campos_adicionales",
    )
    nombre = models.CharField(max_length=300)
    valor = models.CharField(max_length=300)

    class Meta:
        verbose_name = "Campo Adicional de Liquidación"
        verbose_name_plural = "Campos Adicionales de Liquidación"


class LiquidacionLogCambioEstado(models.Model):
    """Bitácora para seguimiento de estados y mensajes SRI."""

    liquidacion = models.ForeignKey(
        LiquidacionCompra,
        on_delete=models.CASCADE,
        related_name="historial_estados",
    )
    estado = models.CharField(max_length=15, choices=LiquidacionCompra.ESTADOS_INTERNOS)
    estado_sri = models.CharField(max_length=15, choices=LiquidacionCompra.ESTADOS_SRI, blank=True)
    mensaje = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de Liquidación"
        verbose_name_plural = "Historial de Liquidaciones"
        ordering = ("-creado_en",)
