from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.validators import MinValueValidator, MaxLengthValidator
from django.utils import timezone
from decimal import Decimal


class GuiaRemision(models.Model):
    """
    Modelo para las Guías de Remisión según normativa SRI Ecuador
    """
    
    # Opciones para motivo de traslado según SRI
    MOTIVOS_TRASLADO = [
        ('01', 'Venta'),
        ('02', 'Transformación'),
        ('03', 'Consignación'),
        ('04', 'Devolución'),
        ('05', 'Otros'),
    ]
    
    # Estados de la guía
    ESTADOS = [
        ('borrador', 'Borrador'),
        ('autorizada', 'Autorizada'),
        ('anulada', 'Anulada'),
        ('devuelta', 'Devuelta'),
    ]
    
    # Campos de numeración SRI
    establecimiento = models.CharField(
        max_length=3, 
        default='001',
        help_text="Código del establecimiento (3 dígitos)"
    )
    punto_emision = models.CharField(
        max_length=3, 
        default='001',
        help_text="Código del punto de emisión (3 dígitos)"
    )
    secuencial = models.CharField(
        max_length=9,
        help_text="Número secuencial (9 dígitos)"
    )
    
    # Datos generales
    fecha_emision = models.DateField(
        default=timezone.now,
        help_text="Fecha de emisión de la guía"
    )
    fecha_inicio_traslado = models.DateTimeField(
        help_text="Fecha y hora de inicio del traslado"
    )
    fecha_fin_traslado = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Fecha y hora de fin del traslado"
    )
    motivo_traslado = models.CharField(
        max_length=2, 
        choices=MOTIVOS_TRASLADO,
        help_text="Motivo del traslado según catálogo SRI"
    )
    
    # Datos del destinatario
    destinatario_identificacion = models.CharField(
        max_length=13,
        help_text="RUC, cédula o pasaporte del destinatario"
    )
    destinatario_nombre = models.CharField(
        max_length=300,
        help_text="Razón social o nombre del destinatario"
    )
    direccion_partida = models.TextField(
        help_text="Dirección desde donde se envía la mercadería"
    )
    direccion_destino = models.TextField(
        help_text="Dirección donde se entrega la mercadería"
    )
    
    # Datos del transportista
    transportista_ruc = models.CharField(
        max_length=13,
        help_text="RUC del transportista"
    )
    transportista_nombre = models.CharField(
        max_length=300,
        help_text="Razón social del transportista"
    )
    placa = models.CharField(
        max_length=10,
        help_text="Placa del vehículo"
    )
    transportista_observaciones = models.TextField(
        blank=True,
        help_text="Observaciones adicionales del transportista"
    )
    
    # Campos SRI para autorización electrónica
    clave_acceso = models.CharField(
        max_length=49, 
        null=True, 
        blank=True,
        unique=True,
        help_text="Clave de acceso SRI (49 dígitos)"
    )
    numero_autorizacion = models.CharField(
        max_length=37, 
        null=True, 
        blank=True,
        help_text="Número de autorización del SRI"
    )
    fecha_autorizacion = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Fecha y hora de autorización del SRI"
    )
    xml_autorizado = models.TextField(
        null=True, 
        blank=True,
        help_text="XML autorizado por el SRI"
    )
    
    # Estado y control
    estado = models.CharField(
        max_length=20, 
        choices=ESTADOS, 
        default='borrador'
    )
    observaciones = models.TextField(
        blank=True,
        help_text="Observaciones generales de la guía"
    )
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    usuario_creacion = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='guias_creadas',
        null=True, 
        blank=True
    )
    usuario_modificacion = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='guias_modificadas',
        null=True, 
        blank=True
    )
    
    class Meta:
        db_table = 'guia_remision'
        verbose_name = 'Guía de Remisión'
        verbose_name_plural = 'Guías de Remisión'
        ordering = ['-fecha_emision', '-secuencial']
        unique_together = [['establecimiento', 'punto_emision', 'secuencial']]
        indexes = [
            models.Index(fields=['fecha_emision']),
            models.Index(fields=['estado']),
            models.Index(fields=['destinatario_identificacion']),
            models.Index(fields=['clave_acceso']),
        ]
    
    def __str__(self):
        return f"Guía {self.numero_completo} - {self.destinatario_nombre}"
    
    @property
    def numero_completo(self):
        """Devuelve el número completo de la guía: 001-001-000000001"""
        return f"{self.establecimiento}-{self.punto_emision}-{self.secuencial.zfill(9)}"
    
    def save(self, *args, **kwargs):
        """Override save para generar secuencial automáticamente"""
        if not self.secuencial:
            # Obtener el último secuencial para este establecimiento y punto de emisión
            ultima_guia = GuiaRemision.objects.filter(
                establecimiento=self.establecimiento,
                punto_emision=self.punto_emision
            ).order_by('-secuencial').first()
            
            if ultima_guia and ultima_guia.secuencial.isdigit():
                nuevo_secuencial = int(ultima_guia.secuencial) + 1
            else:
                nuevo_secuencial = 1
            
            self.secuencial = str(nuevo_secuencial).zfill(9)
        
        super().save(*args, **kwargs)
    
    def puede_editarse(self):
        """Determina si la guía puede editarse"""
        return self.estado == 'borrador'
    
    def puede_anularse(self):
        """Determina si la guía puede anularse"""
        return self.estado in ['borrador', 'autorizada']


class DetalleGuiaRemision(models.Model):
    """
    Modelo para los detalles de productos en la Guía de Remisión
    """
    
    guia = models.ForeignKey(
        GuiaRemision, 
        on_delete=models.CASCADE, 
        related_name='detalles',
        help_text="Guía de remisión a la que pertenece este detalle"
    )
    orden = models.PositiveIntegerField(
        default=1,
        help_text="Orden del producto en la guía"
    )
    
    # Datos del producto
    codigo_producto = models.CharField(
        max_length=50,
        help_text="Código del producto o servicio"
    )
    descripcion_producto = models.CharField(
        max_length=500,
        help_text="Descripción del producto o servicio"
    )
    cantidad = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.0001'))],
        help_text="Cantidad del producto"
    )
    
    # Campos adicionales opcionales
    unidad_medida = models.CharField(
        max_length=20,
        blank=True,
        help_text="Unidad de medida (kg, unidades, etc.)"
    )
    observaciones = models.TextField(
        blank=True,
        help_text="Observaciones específicas del producto"
    )
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'detalle_guia_remision'
        verbose_name = 'Detalle de Guía de Remisión'
        verbose_name_plural = 'Detalles de Guías de Remisión'
        ordering = ['orden', 'id']
        indexes = [
            models.Index(fields=['guia', 'orden']),
            models.Index(fields=['codigo_producto']),
        ]
    
    def __str__(self):
        return f"{self.codigo_producto} - {self.descripcion_producto[:50]}"


class ConfiguracionGuiaRemision(models.Model):
    """
    Modelo para la configuración del módulo de Guías de Remisión
    """
    
    # Configuración de numeración
    establecimiento_defecto = models.CharField(
        max_length=3,
        default='001',
        help_text="Establecimiento por defecto para nuevas guías"
    )
    punto_emision_defecto = models.CharField(
        max_length=3,
        default='001',
        help_text="Punto de emisión por defecto para nuevas guías"
    )
    
    # Configuración de empresa
    nombre_comercial = models.CharField(
        max_length=300,
        blank=True,
        help_text="Nombre comercial para los documentos"
    )
    direccion_matriz = models.TextField(
        blank=True,
        help_text="Dirección de la matriz para las guías"
    )
    
    # Configuración SRI
    ambiente_sri = models.CharField(
        max_length=1,
        choices=[('1', 'Pruebas'), ('2', 'Producción')],
        default='1',
        help_text="Ambiente del SRI"
    )
    tipo_emision = models.CharField(
        max_length=1,
        choices=[('1', 'Emisión Normal'), ('2', 'Emisión por Indisponibilidad')],
        default='1',
        help_text="Tipo de emisión"
    )
    
    # Configuración de plantilla PDF
    mostrar_logo = models.BooleanField(
        default=True,
        help_text="Mostrar logo en el PDF"
    )
    ruta_logo = models.CharField(
        max_length=255,
        blank=True,
        help_text="Ruta del archivo de logo"
    )
    
    # Campos de auditoría
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    usuario_modificacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'configuracion_guia_remision'
        verbose_name = 'Configuración de Guías de Remisión'
        verbose_name_plural = 'Configuraciones de Guías de Remisión'
    
    def __str__(self):
        return f"Configuración Guías de Remisión - {self.establecimiento_defecto}-{self.punto_emision_defecto}"
    
    @classmethod
    def get_configuracion(cls):
        """Obtiene la configuración activa, crea una por defecto si no existe"""
        config, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'establecimiento_defecto': '001',
                'punto_emision_defecto': '001',
                'ambiente_sri': '1',
                'tipo_emision': '1',
                'mostrar_logo': True,
            }
        )
        return config
