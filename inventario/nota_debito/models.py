"""Modelos para Notas de Débito Electrónicas
Documento SRI: codDoc 05

Estructura inspirada en `inventario/nota_credito/models.py`.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from inventario.models import Cliente, Empresa, Factura, TenantManager


class NotaDebito(models.Model):
    """Nota de Débito Electrónica.

    Incrementa/ajusta valores de una factura previamente autorizada.
    """

    ESTADO_SRI_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ENVIADO', 'Enviado'),
        ('RECIBIDA', 'Recibida'),
        ('RECIBIDO', 'Recibido'),
        ('AUTORIZADO', 'Autorizado'),
        ('RECHAZADO', 'Rechazado'),
        ('ANULADO', 'Anulado'),
    ]

    # Tenant/Empresa
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='notas_debito')

    objects = TenantManager()
    _unsafe_objects = models.Manager()

    # Relación con factura original
    factura_modificada = models.ForeignKey(
        Factura,
        on_delete=models.PROTECT,
        related_name='notas_debito',
        help_text='Factura que se está modificando',
    )

    # Datos del comprobante
    establecimiento = models.CharField(max_length=3, default='001')
    punto_emision = models.CharField(max_length=3, default='001')
    secuencial = models.CharField(max_length=9)

    # Clave de acceso / autorización
    clave_acceso = models.CharField(max_length=49, unique=True, blank=True, null=True)
    numero_autorizacion = models.CharField(max_length=49, blank=True, null=True)
    fecha_autorizacion = models.DateTimeField(blank=True, null=True)

    # Fechas
    fecha_emision = models.DateField()

    # Documento modificado
    cod_doc_modificado = models.CharField(max_length=2, default='01')
    num_doc_modificado = models.CharField(max_length=17)
    fecha_emision_doc_sustento = models.DateField()

    # Motivo
    motivo = models.CharField(max_length=300)

    # Totales
    subtotal_sin_impuestos = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    total_iva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    valor_modificacion = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Valor total de la nota de débito',
    )

    estado_sri = models.CharField(max_length=20, choices=ESTADO_SRI_CHOICES, default='PENDIENTE')
    mensaje_sri = models.TextField(blank=True, null=True)
    email_enviado = models.BooleanField(
        default=False,
        help_text='Indica si ya se envió el correo con XML/RIDE de la nota de débito',
    )
    email_enviado_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='Fecha/hora del primer envío exitoso de la nota de débito',
    )
    email_envio_intentos = models.PositiveSmallIntegerField(
        default=0,
        help_text='Número de intentos de envío de la nota de débito',
    )
    email_ultimo_error = models.TextField(
        blank=True,
        null=True,
        help_text='Último error registrado al intentar enviar correo de la nota de débito',
    )

    # Auditoría
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='notas_debito_creadas',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas_debito_usuario',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Nota de Débito'
        verbose_name_plural = 'Notas de Débito'
        ordering = ['-fecha_emision', '-secuencial']
        unique_together = ['empresa', 'establecimiento', 'punto_emision', 'secuencial']

    def __str__(self) -> str:
        return f"ND {self.numero_completo} - {self.factura_modificada}"

    @property
    def numero_completo(self) -> str:
        return f"{self.establecimiento}-{self.punto_emision}-{self.secuencial}"


class DetalleNotaDebito(models.Model):
    """Detalle (línea) de la Nota de Débito."""

    nota_debito = models.ForeignKey(NotaDebito, on_delete=models.CASCADE, related_name='detalles')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='detalles_notas_debito')

    codigo_principal = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=300)

    cantidad = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    descuento = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    codigo_iva = models.CharField(max_length=2, default='2')
    tarifa_iva = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    base_imponible = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_iva = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Detalle Nota de Débito'
        verbose_name_plural = 'Detalles Nota de Débito'


class TotalImpuestoNotaDebito(models.Model):
    """Totales de impuestos para la Nota de Débito (para XML)."""

    nota_debito = models.ForeignKey(NotaDebito, on_delete=models.CASCADE, related_name='totales_impuestos')

    codigo = models.CharField(max_length=2, default='2')
    codigo_porcentaje = models.CharField(max_length=2, default='2')
    tarifa = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    base_imponible = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Total Impuesto Nota de Débito'
        verbose_name_plural = 'Totales Impuestos Nota de Débito'
