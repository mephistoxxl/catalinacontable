from django.db import models
from inventario.models import Empresa, Proveedor, Usuario
from django.utils import timezone
from decimal import Decimal

# Asumimos que LiquidacionCompra existe en inventario.models, o si no se usa una referencia genérica.
# Si no existe, podemos usar models.CharField para referencia o buscar si existe FacturaCompra.
# Por ahora usaré una referencia opcional a 'LiquidacionCompra' si existe, o solo campos manuales.
# Revisando models.py de inventario, buscaremos LiquidacionCompra.

class CuentaPagar(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADA_PARCIAL', 'Pagada Parcialmente'),
        ('PAGADA', 'Pagada'),
        ('VENCIDA', 'Vencida')
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='cuentas_pagar')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name='cuentas_pagar')
    
    # Referencia al documento origen (puede ser número de factura proveedor o link a modelo liquidación)
    referencia_documento = models.CharField(max_length=100, help_text="Número de factura del proveedor o documento relacionado")
    # Opcional: Relación con liquidación de compra si existiera en el futuro
    # liquidacion_compra = models.OneToOneField('inventario.LiquidacionCompra', null=True, blank=True, ...)

    fecha_emision = models.DateField(default=timezone.now)
    fecha_vencimiento = models.DateField()
    
    monto_total = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    saldo_pendiente = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    observaciones = models.TextField(blank=True, null=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Actualizar estado basado en el saldo y vencimiento
        if self.saldo_pendiente <= Decimal('0.00'):
            self.estado = 'PAGADA'
            self.saldo_pendiente = Decimal('0.00')
        elif self.saldo_pendiente < self.monto_total:
            self.estado = 'PAGADA_PARCIAL'
        elif self.fecha_vencimiento < timezone.now().date() and self.saldo_pendiente > 0:
            self.estado = 'VENCIDA'
        else:
            self.estado = 'PENDIENTE'
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"CxP - {self.proveedor.razon_social} - {self.saldo_pendiente}"

    class Meta:
        verbose_name = "Cuenta por Pagar"
        verbose_name_plural = "Cuentas por Pagar"
        ordering = ['-fecha_emision']

class PagoProveedor(models.Model):
    METODOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('CHEQUE', 'Cheque'),
        ('TARJETA', 'Tarjeta de Crédito/Débito'),
        ('OTRO', 'Otro')
    ]

    cuenta = models.ForeignKey(CuentaPagar, on_delete=models.CASCADE, related_name='pagos')
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    
    fecha_pago = models.DateField(default=timezone.now)
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='TRANSFERENCIA')
    referencia_pago = models.CharField(max_length=100, blank=True, null=True, help_text="Número de transferencia, cheque, etc.")
    observaciones = models.TextField(blank=True, null=True)
    
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Al guardar un pago nuevo, actualizar el saldo de la cuenta por pagar
        if is_new:
            cuenta = self.cuenta
            # Recalcular saldo pendiente
            todos_pagos = cuenta.pagos.aggregate(total=models.Sum('monto'))['total'] or Decimal('0.00')
            cuenta.saldo_pendiente = cuenta.monto_total - todos_pagos
            cuenta.save() 

    def delete(self, *args, **kwargs):
        cuenta = self.cuenta
        super().delete(*args, **kwargs)
        # Recalcular saldo pendiente al eliminar un pago
        todos_pagos = cuenta.pagos.aggregate(total=models.Sum('monto'))['total'] or Decimal('0.00')
        cuenta.saldo_pendiente = cuenta.monto_total - todos_pagos
        cuenta.save()

    def __str__(self):
        return f"Pago de {self.monto} a cuenta {self.cuenta.id}"

    class Meta:
        verbose_name = "Pago a Proveedor"
        verbose_name_plural = "Pagos a Proveedores"
        ordering = ['-fecha_pago', '-id']