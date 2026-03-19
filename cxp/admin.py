from django.contrib import admin
from .models import CuentaPagar, PagoProveedor

@admin.register(CuentaPagar)
class CuentaPagarAdmin(admin.ModelAdmin):
    list_display = ('proveedor', 'empresa', 'fecha_emision', 'fecha_vencimiento', 'monto_total', 'saldo_pendiente', 'estado')
    list_filter = ('estado', 'fecha_vencimiento', 'empresa')
    search_fields = ('proveedor__razon_social', 'proveedor__identificacion')

@admin.register(PagoProveedor)
class PagoProveedorAdmin(admin.ModelAdmin):
    list_display = ('cuenta', 'fecha_pago', 'monto', 'metodo_pago')
    list_filter = ('fecha_pago', 'metodo_pago')