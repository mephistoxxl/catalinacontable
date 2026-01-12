"""Admin para Nota de Débito."""

from __future__ import annotations

from django.contrib import admin

from .models import DetalleNotaDebito, NotaDebito, TotalImpuestoNotaDebito


@admin.register(NotaDebito)
class NotaDebitoAdmin(admin.ModelAdmin):
    list_display = ('id', 'empresa', 'numero_completo', 'fecha_emision', 'estado_sri', 'valor_modificacion')
    list_filter = ('estado_sri', 'empresa')
    search_fields = ('secuencial', 'num_doc_modificado', 'clave_acceso', 'numero_autorizacion')


@admin.register(DetalleNotaDebito)
class DetalleNotaDebitoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nota_debito', 'codigo_principal', 'descripcion', 'cantidad', 'total')


@admin.register(TotalImpuestoNotaDebito)
class TotalImpuestoNotaDebitoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nota_debito', 'codigo', 'codigo_porcentaje', 'tarifa', 'base_imponible', 'valor')
