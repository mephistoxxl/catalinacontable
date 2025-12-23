"""
Admin para Notas de Crédito
"""
from django.contrib import admin
from .models import NotaCredito, DetalleNotaCredito, TotalImpuestoNotaCredito


class DetalleNotaCreditoInline(admin.TabularInline):
    model = DetalleNotaCredito
    extra = 0
    readonly_fields = ['precio_total_sin_impuesto', 'valor_iva']


class TotalImpuestoNotaCreditoInline(admin.TabularInline):
    model = TotalImpuestoNotaCredito
    extra = 0


@admin.register(NotaCredito)
class NotaCreditoAdmin(admin.ModelAdmin):
    list_display = [
        'numero_completo', 
        'fecha_emision', 
        'factura_modificada',
        'valor_modificacion', 
        'estado_sri',
        'empresa'
    ]
    list_filter = ['estado_sri', 'fecha_emision', 'empresa']
    search_fields = ['secuencial', 'clave_acceso', 'factura_modificada__secuencia']
    readonly_fields = [
        'clave_acceso', 
        'numero_autorizacion', 
        'fecha_autorizacion',
        'fecha_creacion',
        'fecha_modificacion'
    ]
    inlines = [DetalleNotaCreditoInline, TotalImpuestoNotaCreditoInline]
    
    fieldsets = (
        ('Información General', {
            'fields': (
                'empresa',
                'factura_modificada',
                ('establecimiento', 'punto_emision', 'secuencial'),
                'fecha_emision',
            )
        }),
        ('Motivo', {
            'fields': (
                'tipo_motivo',
                'motivo',
                'observaciones',
            )
        }),
        ('Valores', {
            'fields': (
                'subtotal_sin_impuestos',
                ('subtotal_iva_0', 'subtotal_iva_15'),
                'total_iva',
                'valor_modificacion',
            )
        }),
        ('Estado SRI', {
            'fields': (
                'estado_sri',
                'clave_acceso',
                'numero_autorizacion',
                'fecha_autorizacion',
                'mensaje_sri',
            )
        }),
        ('Auditoría', {
            'fields': (
                'creado_por',
                'fecha_creacion',
                'fecha_modificacion',
            ),
            'classes': ('collapse',)
        }),
    )


@admin.register(DetalleNotaCredito)
class DetalleNotaCreditoAdmin(admin.ModelAdmin):
    list_display = ['nota_credito', 'codigo_principal', 'descripcion', 'cantidad', 'precio_unitario', 'precio_total_sin_impuesto']
    list_filter = ['nota_credito__empresa']
    search_fields = ['codigo_principal', 'descripcion']


@admin.register(TotalImpuestoNotaCredito)
class TotalImpuestoNotaCreditoAdmin(admin.ModelAdmin):
    list_display = ['nota_credito', 'codigo', 'tarifa', 'base_imponible', 'valor']
    list_filter = ['codigo', 'tarifa']
