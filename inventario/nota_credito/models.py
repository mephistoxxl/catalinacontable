"""
Modelos para Notas de Crédito Electrónicas
Documento SRI: codDoc 04
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from decimal import Decimal
from inventario.models import Empresa, Factura, Cliente, TenantManager


class NotaCredito(models.Model):
    """
    Nota de Crédito Electrónica
    Modifica una factura previamente autorizada por el SRI
    """
    
    ESTADO_SRI_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ENVIADO', 'Enviado'),
        ('RECIBIDO', 'Recibido'),
        ('AUTORIZADO', 'Autorizado'),
        ('RECHAZADO', 'Rechazado'),
        ('ANULADO', 'Anulado'),
    ]
    
    MOTIVO_CHOICES = [
        ('DEVOLUCION', 'Devolución de mercadería'),
        ('DESCUENTO', 'Descuento posterior a la venta'),
        ('ANULACION', 'Anulación de factura'),
        ('CORRECCION', 'Corrección de valores'),
        ('OTRO', 'Otro motivo'),
    ]
    
    # Tenant/Empresa
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='notas_credito'
    )
    
    # Managers
    objects = TenantManager()
    _unsafe_objects = models.Manager()
    
    # ========== RELACIÓN CON FACTURA ORIGINAL ==========
    factura_modificada = models.ForeignKey(
        Factura,
        on_delete=models.PROTECT,
        related_name='notas_credito',
        help_text="Factura que se está modificando"
    )
    
    # ========== DATOS DEL COMPROBANTE ==========
    establecimiento = models.CharField(
        max_length=3,
        default='001',
        help_text="Código del establecimiento (3 dígitos)"
    )
    punto_emision = models.CharField(
        max_length=3,
        default='001',
        help_text="Punto de emisión (3 dígitos)"
    )
    secuencial = models.CharField(
        max_length=9,
        help_text="Número secuencial (9 dígitos)"
    )
    
    # ========== CLAVE DE ACCESO Y AUTORIZACIÓN ==========
    clave_acceso = models.CharField(
        max_length=49,
        unique=True,
        blank=True,
        null=True,
        help_text="Clave de acceso de 49 dígitos"
    )
    numero_autorizacion = models.CharField(
        max_length=49,
        blank=True,
        null=True,
        help_text="Número de autorización del SRI"
    )
    fecha_autorizacion = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Fecha y hora de autorización"
    )
    
    # ========== FECHAS ==========
    fecha_emision = models.DateField(
        help_text="Fecha de emisión de la nota de crédito"
    )
    
    # ========== DATOS DEL DOCUMENTO MODIFICADO ==========
    # Estos campos se copian de la factura para el XML
    cod_doc_modificado = models.CharField(
        max_length=2,
        default='01',
        help_text="Código del documento modificado (01=Factura)"
    )
    num_doc_modificado = models.CharField(
        max_length=17,
        help_text="Número completo del documento: 001-001-000000001"
    )
    fecha_emision_doc_sustento = models.DateField(
        help_text="Fecha de emisión de la factura original"
    )
    
    # ========== MOTIVO ==========
    tipo_motivo = models.CharField(
        max_length=20,
        choices=MOTIVO_CHOICES,
        default='DEVOLUCION'
    )
    motivo = models.CharField(
        max_length=300,
        help_text="Descripción del motivo de la nota de crédito"
    )
    
    # ========== VALORES MONETARIOS ==========
    subtotal_sin_impuestos = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Subtotal sin impuestos"
    )
    
    # Subtotales por tarifa de IVA
    subtotal_iva_0 = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Subtotal con IVA 0%"
    )
    subtotal_iva_5 = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Subtotal con IVA 5%"
    )
    subtotal_iva_12 = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Subtotal con IVA 12%"
    )
    subtotal_iva_15 = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Subtotal con IVA 15%"
    )
    subtotal_no_objeto_iva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Subtotal no objeto de IVA"
    )
    subtotal_exento_iva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Subtotal exento de IVA"
    )
    
    total_iva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total del IVA"
    )
    
    # Alias para compatibilidad con templates
    @property
    def subtotal_cero(self):
        """Alias para subtotal_iva_0"""
        return self.subtotal_iva_0
    
    @property
    def subtotal_iva(self):
        """Alias: subtotal con IVA 15% (o cualquier tarifa vigente)"""
        return self.subtotal_iva_15 + self.subtotal_iva_12 + self.subtotal_iva_5
    
    @property
    def valor_iva(self):
        """Alias para total_iva"""
        return self.total_iva
    
    @property
    def total_sin_impuestos(self):
        """Alias para subtotal_sin_impuestos"""
        return self.subtotal_sin_impuestos
    
    valor_modificacion = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Valor total de la nota de crédito"
    )
    
    # ========== OBSERVACIONES ==========
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Observaciones adicionales"
    )
    
    # ========== ESTADO ==========
    estado_sri = models.CharField(
        max_length=20,
        choices=ESTADO_SRI_CHOICES,
        default='PENDIENTE'
    )
    
    mensaje_sri = models.TextField(
        blank=True,
        null=True,
        help_text="Mensaje de respuesta del SRI"
    )
    
    # ========== CONTROL DE INVENTARIO ==========
    inventario_actualizado = models.BooleanField(
        default=False,
        help_text="Indica si ya se actualizó el inventario (devoluciones)"
    )
    
    # ========== AUDITORÍA ==========
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='notas_credito_creadas'
    )
    # Alias para compatibilidad
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas_credito_usuario'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Nota de Crédito"
        verbose_name_plural = "Notas de Crédito"
        ordering = ['-fecha_emision', '-secuencial']
        unique_together = ['empresa', 'establecimiento', 'punto_emision', 'secuencial']
    
    def __str__(self):
        return f"NC {self.numero_completo} - {self.factura_modificada}"
    
    @property
    def numero_completo(self):
        """Retorna el número completo de la NC: 001-001-000000001"""
        return f"{self.establecimiento}-{self.punto_emision}-{self.secuencial}"
    
    def clean(self):
        """
        Validaciones del modelo - Controles críticos para evitar Error 68 del SRI
        
        Los 3 "candados" obligatorios según Tabla 14 SRI:
        1. codDocModificado = '01' (Factura)
        2. numDocModificado = número exacto de la factura
        3. fechaEmisionDocSustento = fecha exacta de la factura
        """
        from django.core.exceptions import ValidationError
        
        errors = {}
        
        # ========== VALIDACIÓN 1: Factura debe existir ==========
        if not self.factura_modificada_id and not self.factura_modificada:
            errors['factura_modificada'] = 'Debe seleccionar una factura válida.'
        
        if self.factura_modificada:
            factura = self.factura_modificada
            
            # ========== VALIDACIÓN 2: Factura debe estar AUTORIZADA ==========
            if factura.estado_sri not in ['AUTORIZADO', 'AUTORIZADA']:
                errors['factura_modificada'] = (
                    'Solo se pueden emitir notas de crédito para facturas AUTORIZADAS por el SRI. '
                    f'Estado actual: {factura.estado_sri}'
                )
            
            # ========== VALIDACIÓN 3: Factura debe tener clave de acceso ==========
            if not factura.clave_acceso:
                errors['factura_modificada'] = (
                    'La factura no tiene clave de acceso del SRI. '
                    'Esto causará Error 68: Documento sustento no existe.'
                )
            
            # ========== VALIDACIÓN 4: Saldo disponible ==========
            if hasattr(factura, 'saldo_nota_credito'):
                from decimal import ROUND_HALF_UP

                saldo_disponible = factura.saldo_nota_credito
                valor_mod = self.valor_modificacion
                if valor_mod is not None:
                    saldo_q = Decimal(str(saldo_disponible)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    valor_q = Decimal(str(valor_mod)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    tolerancia = Decimal('0.01')

                    if valor_q > (saldo_q + tolerancia):
                        errors['valor_modificacion'] = (
                            f'El valor (${valor_q}) excede el saldo disponible '
                            f'de la factura (${saldo_q}).'
                        )
            
            # ========== VALIDACIÓN 5: Fecha NC no anterior a fecha factura ==========
            if self.fecha_emision and factura.fecha_emision:
                if self.fecha_emision < factura.fecha_emision:
                    errors['fecha_emision'] = (
                        'La fecha de la NC no puede ser anterior a la fecha de la factura '
                        f'({factura.fecha_emision.strftime("%d/%m/%Y")}).'
                    )
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        # ========== AUTO-COPIAR DATOS DE LA FACTURA (Candados SRI) ==========
        # Estos datos se copian automáticamente para evitar errores manuales
        if self.factura_modificada:
            # Siempre sobrescribir para garantizar consistencia
            self.cod_doc_modificado = '01'  # Factura
            self.num_doc_modificado = self.factura_modificada.numero_completo
            self.fecha_emision_doc_sustento = self.factura_modificada.fecha_emision
        
        # Validar antes de guardar
        self.full_clean()
        
        super().save(*args, **kwargs)
    
    def actualizar_inventario(self):
        """
        Actualiza el inventario si es una devolución
        Solo se ejecuta una vez
        """
        if self.inventario_actualizado:
            return False
        
        if self.tipo_motivo in ['DEVOLUCION', 'ANULACION']:
            for detalle in self.detalles.all():
                if detalle.producto and detalle.producto.tiene_inventario:
                    detalle.producto.disponible = (detalle.producto.disponible or 0) + detalle.cantidad
                    detalle.producto.save()
            
            self.inventario_actualizado = True
            self.save(update_fields=['inventario_actualizado'])
            return True
        
        return False


class DetalleNotaCredito(models.Model):
    """
    Detalle de productos/servicios de la Nota de Crédito
    """
    
    nota_credito = models.ForeignKey(
        NotaCredito,
        on_delete=models.CASCADE,
        related_name='detalles'
    )
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE
    )
    
    # Managers
    objects = TenantManager()
    _unsafe_objects = models.Manager()
    
    # Producto/Servicio (puede ser NULL si es un ajuste genérico)
    producto = models.ForeignKey(
        'inventario.Producto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    servicio = models.ForeignKey(
        'inventario.Servicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Datos del ítem
    codigo_principal = models.CharField(max_length=25)
    codigo_auxiliar = models.CharField(max_length=25, blank=True, null=True)
    descripcion = models.CharField(max_length=300)
    
    # Cantidades y precios
    cantidad = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.000001'))]
    )
    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    descuento = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00')
    )
    precio_total_sin_impuesto = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )
    
    # IVA
    codigo_iva = models.CharField(
        max_length=2,
        default='4',
        help_text="Código de IVA: 0=0%, 2=12%, 3=14%, 4=15%, 5=5%, 6=No objeto, 7=Exento"
    )
    tarifa_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('15.00')
    )
    valor_iva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    class Meta:
        verbose_name = "Detalle de Nota de Crédito"
        verbose_name_plural = "Detalles de Nota de Crédito"
    
    def __str__(self):
        return f"{self.codigo_principal} - {self.descripcion[:50]}"
    
    def save(self, *args, **kwargs):
        # Normalizar tarifa IVA según código (evita inconsistencias tipo codigo=2 con tarifa=15)
        try:
            tarifa_por_codigo = {
                '0': Decimal('0'),
                '2': Decimal('12'),
                '3': Decimal('14'),
                '4': Decimal('15'),
                '5': Decimal('5'),
                '6': Decimal('0'),
                '7': Decimal('0'),
                '8': Decimal('0'),
                '10': Decimal('13'),
            }
            codigo = str(self.codigo_iva or '').strip()
            if codigo in tarifa_por_codigo:
                self.tarifa_iva = tarifa_por_codigo[codigo]
        except Exception:
            pass

        # Calcular precio total sin impuesto
        self.precio_total_sin_impuesto = (self.cantidad * self.precio_unitario) - self.descuento
        
        # Calcular IVA
        tarifa_decimal = self.tarifa_iva / Decimal('100')
        self.valor_iva = self.precio_total_sin_impuesto * tarifa_decimal
        
        super().save(*args, **kwargs)


class TotalImpuestoNotaCredito(models.Model):
    """
    Totales de impuestos para la Nota de Crédito
    Similar a TotalImpuestoFactura
    """
    
    nota_credito = models.ForeignKey(
        NotaCredito,
        on_delete=models.CASCADE,
        related_name='totales_impuestos'
    )
    
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE
    )
    
    # Managers
    objects = TenantManager()
    _unsafe_objects = models.Manager()
    
    codigo = models.CharField(
        max_length=2,
        default='2',
        help_text="Código del impuesto (2=IVA, 3=ICE, 5=IRBPNR)"
    )
    codigo_porcentaje = models.CharField(
        max_length=4,
        help_text="Código del porcentaje de IVA"
    )
    tarifa = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    base_imponible = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )
    valor = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )
    
    class Meta:
        verbose_name = "Total Impuesto NC"
        verbose_name_plural = "Totales Impuestos NC"
    
    def __str__(self):
        return f"IVA {self.tarifa}%: Base {self.base_imponible} - Valor {self.valor}"
