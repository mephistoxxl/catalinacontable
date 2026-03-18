from django.db import models
from inventario.models import Empresa, Cliente, Factura, Usuario
from django.utils import timezone
from decimal import Decimal

class CuentaCobrar(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADA_PARCIAL', 'Pagada Parcialmente'),
        ('PAGADA', 'Pagada'),
        ('VENCIDA', 'Vencida')
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='cuentas_cobrar')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='cuentas_cobrar')
    factura = models.OneToOneField(Factura, on_delete=models.SET_NULL, null=True, blank=True, related_name='cuenta_cobrar')
    
    fecha_emision = models.DateField(default=timezone.now)
    fecha_vencimiento = models.DateField()
    
    monto_total = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    saldo_pendiente = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    observaciones = models.TextField(blank=True, null=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Actualizar estado basado en el saldo y vencimiento
        if self.saldo_pendiente <= Decimal('0.00'):
            self.estado = 'PAGADA'
        elif self.saldo_pendiente < self.monto_total:
            self.estado = 'PAGADA_PARCIAL'
        elif self.fecha_vencimiento < timezone.now().date() and self.saldo_pendiente > 0:
            self.estado = 'VENCIDA'
        else:
            self.estado = 'PENDIENTE'
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"CxC - {self.cliente.razon_social} - {self.saldo_pendiente}"

    class Meta:
        verbose_name = "Cuenta por Cobrar"
        verbose_name_plural = "Cuentas por Cobrar"
        ordering = ['-fecha_emision']

class Abono(models.Model):
    METODOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('CHEQUE', 'Cheque'),
        ('TARJETA', 'Tarjeta de Crédito/Débito'),
        ('OTRO', 'Otro')
    ]

    cuenta = models.ForeignKey(CuentaCobrar, on_delete=models.CASCADE, related_name='abonos')
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
        
        # Al guardar un abono nuevo, actualizar el saldo de la cuenta por cobrar
        if is_new:
            cuenta = self.cuenta
            # Recalcular saldo pendiente
            todos_abonos = cuenta.abonos.aggregate(total=models.Sum('monto'))['total'] or Decimal('0.00')
            cuenta.saldo_pendiente = cuenta.monto_total - todos_abonos
            cuenta.save() # Esto también actualizará el estado de la cuenta.

    def delete(self, *args, **kwargs):
        cuenta = self.cuenta
        super().delete(*args, **kwargs)
        # Recalcular saldo pendiente al eliminar un abono
        todos_abonos = cuenta.abonos.aggregate(total=models.Sum('monto'))['total'] or Decimal('0.00')
        cuenta.saldo_pendiente = cuenta.monto_total - todos_abonos
        cuenta.save()

    def __str__(self):
        return f"Abono de {self.monto} a cuenta {self.cuenta.id}"

    class Meta:
        verbose_name = "Abono"
        verbose_name_plural = "Abonos"
        ordering = ['-fecha_pago', '-id']
