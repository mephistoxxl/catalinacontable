"""
Modelos para el sistema de planes de facturación
"""
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date, timedelta


class Plan(models.Model):
    """Plan de facturación con límites de documentos"""
    
    PLANES_CHOICES = [
        ('MICRO', 'Plan Micro'),
        ('BASICO', 'Plan Básico'),
        ('EMPRENDEDOR', 'Plan Emprendedor'),
        ('EXTRA', 'Opción Extra'),
    ]
    
    codigo = models.CharField(
        max_length=20,
        choices=PLANES_CHOICES,
        unique=True,
        verbose_name='Código del Plan'
    )
    nombre = models.CharField(
        max_length=100,
        verbose_name='Nombre del Plan'
    )
    precio_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Precio Base (sin IVA)'
    )
    limite_documentos = models.PositiveIntegerField(
        verbose_name='Límite de Documentos',
        help_text='Número máximo de documentos que se pueden autorizar al mes/año'
    )
    frecuencia = models.CharField(
        max_length=20,
        choices=[
            ('MENSUAL', 'Mensual'),
            ('ANUAL', 'Anual'),
        ],
        default='ANUAL',
        verbose_name='Frecuencia de Cobro'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Plan Activo'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción'
    )
    
    class Meta:
        verbose_name = 'Plan de Facturación'
        verbose_name_plural = 'Planes de Facturación'
        ordering = ['precio_base']
    
    def __str__(self):
        return f"{self.nombre} - {self.limite_documentos} docs/{self.frecuencia.lower()}"
    
    @property
    def precio_con_iva(self):
        """Calcula el precio con IVA (15%)"""
        iva = self.precio_base * Decimal('0.15')
        return self.precio_base + iva


class EmpresaPlan(models.Model):
    """Relación entre empresa y su plan actual"""
    
    empresa = models.OneToOneField(
        'inventario.Empresa',
        on_delete=models.CASCADE,
        related_name='plan_activo',
        verbose_name='Empresa'
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='empresas',
        verbose_name='Plan Actual'
    )
    fecha_inicio = models.DateField(
        default=date.today,
        verbose_name='Fecha de Inicio'
    )
    fecha_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Finalización',
        help_text='Se calcula automáticamente según la frecuencia del plan'
    )
    documentos_autorizados = models.PositiveIntegerField(
        default=0,
        verbose_name='Documentos Autorizados',
        help_text='Contador de documentos autorizados en el periodo actual'
    )
    ultimo_reset = models.DateField(
        default=date.today,
        verbose_name='Último Reseteo',
        help_text='Última vez que se reinició el contador'
    )
    notificacion_enviada = models.BooleanField(
        default=False,
        verbose_name='Notificación Enviada',
        help_text='Se envió notificación al alcanzar el 80% del límite'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Plan Activo'
    )
    
    class Meta:
        verbose_name = 'Plan de Empresa'
        verbose_name_plural = 'Planes de Empresas'
    
    def __str__(self):
        return f"{self.empresa.razon_social} - {self.plan.nombre}"
    
    def save(self, *args, **kwargs):
        """Calcular fecha_fin automáticamente si no está definida"""
        if not self.fecha_fin:
            if self.plan.frecuencia == 'MENSUAL':
                self.fecha_fin = self.fecha_inicio + timedelta(days=30)
            else:  # ANUAL
                self.fecha_fin = self.fecha_inicio + timedelta(days=365)
        super().save(*args, **kwargs)
    
    def incrementar_contador(self):
        """Incrementa el contador de documentos autorizados"""
        self.documentos_autorizados += 1
        self.save(update_fields=['documentos_autorizados'])
    
    def resetear_contador(self):
        """Resetea el contador (se ejecuta al inicio de cada periodo)"""
        self.documentos_autorizados = 0
        self.notificacion_enviada = False
        self.ultimo_reset = date.today()
        
        # Calcular nueva fecha_fin
        if self.plan.frecuencia == 'MENSUAL':
            self.fecha_fin = date.today() + timedelta(days=30)
        else:  # ANUAL
            self.fecha_fin = date.today() + timedelta(days=365)
        
        self.save(update_fields=['documentos_autorizados', 'notificacion_enviada', 'ultimo_reset', 'fecha_fin'])
    
    def verificar_limite(self):
        """
        Verifica si se ha alcanzado el límite de documentos.
        Retorna un dict con el estado.
        """
        limite = self.plan.limite_documentos
        usados = self.documentos_autorizados
        porcentaje = (usados / limite * 100) if limite > 0 else 0
        
        return {
            'puede_autorizar': usados < limite,
            'documentos_usados': usados,
            'limite_documentos': limite,
            'porcentaje_usado': round(porcentaje, 2),
            'documentos_restantes': max(0, limite - usados),
            'alcanzado_80': porcentaje >= 80,
            'alcanzado_limite': usados >= limite,
        }
    
    @property
    def periodo_vencido(self):
        """Verifica si el periodo del plan ha vencido"""
        return date.today() > self.fecha_fin if self.fecha_fin else False
    
    @property
    def dias_restantes(self):
        """Calcula los días restantes del periodo"""
        if self.fecha_fin:
            delta = self.fecha_fin - date.today()
            return max(0, delta.days)
        return 0


class HistorialPlan(models.Model):
    """Historial de cambios de plan de una empresa"""
    
    empresa = models.ForeignKey(
        'inventario.Empresa',
        on_delete=models.CASCADE,
        related_name='historial_planes',
        verbose_name='Empresa'
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        verbose_name='Plan'
    )
    fecha_inicio = models.DateField(verbose_name='Fecha de Inicio')
    fecha_fin = models.DateField(verbose_name='Fecha de Fin')
    documentos_autorizados = models.PositiveIntegerField(
        default=0,
        verbose_name='Documentos Autorizados en el Periodo'
    )
    observaciones = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observaciones'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Historial de Plan'
        verbose_name_plural = 'Historial de Planes'
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return f"{self.empresa.razon_social} - {self.plan.nombre} ({self.fecha_inicio} - {self.fecha_fin})"
