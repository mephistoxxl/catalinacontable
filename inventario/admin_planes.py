"""
Configuración del admin para el sistema de planes
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models_planes import Plan, EmpresaPlan, HistorialPlan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'precio_base_formatted', 'precio_con_iva_formatted', 'limite_documentos', 'frecuencia', 'activo']
    list_filter = ['frecuencia', 'activo']
    search_fields = ['nombre', 'codigo']
    readonly_fields = ['precio_con_iva_display']
    
    fieldsets = (
        ('Información del Plan', {
            'fields': ('codigo', 'nombre', 'descripcion')
        }),
        ('Precio y Límites', {
            'fields': ('precio_base', 'precio_con_iva_display', 'limite_documentos', 'frecuencia')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )
    
    def precio_base_formatted(self, obj):
        return f"${obj.precio_base:.2f}"
    precio_base_formatted.short_description = 'Precio Base'
    precio_base_formatted.admin_order_field = 'precio_base'
    
    def precio_con_iva_formatted(self, obj):
        return f"${obj.precio_con_iva:.2f}"
    precio_con_iva_formatted.short_description = 'Precio + IVA (15%)'
    
    def precio_con_iva_display(self, obj):
        if obj.pk:
            return format_html(
                '<strong>${:.2f}</strong> <small class="text-muted">(Base: ${:.2f} + IVA: ${:.2f})</small>',
                obj.precio_con_iva,
                obj.precio_base,
                obj.precio_con_iva - obj.precio_base
            )
        return '-'
    precio_con_iva_display.short_description = 'Precio con IVA'


@admin.register(EmpresaPlan)
class EmpresaPlanAdmin(admin.ModelAdmin):
    list_display = [
        'empresa_info',
        'plan',
        'documentos_usados_display',
        'porcentaje_usado_display',
        'periodo_display',
        'estado_display',
        'acciones'
    ]
    list_filter = ['plan', 'activo', 'notificacion_enviada']
    search_fields = ['empresa__razon_social', 'empresa__ruc']
    readonly_fields = [
        'documentos_autorizados',
        'ultimo_reset',
        'estadisticas_display',
        'periodo_info_display'
    ]
    
    fieldsets = (
        ('Empresa y Plan', {
            'fields': ('empresa', 'plan', 'activo')
        }),
        ('Periodo del Plan', {
            'fields': ('fecha_inicio', 'fecha_fin', 'periodo_info_display')
        }),
        ('Uso del Plan', {
            'fields': ('documentos_autorizados', 'ultimo_reset', 'estadisticas_display', 'notificacion_enviada')
        }),
    )
    
    actions = ['resetear_contadores', 'enviar_notificaciones']
    
    def empresa_info(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>{}</small>',
            obj.empresa.razon_social,
            obj.empresa.ruc
        )
    empresa_info.short_description = 'Empresa'
    
    def documentos_usados_display(self, obj):
        estado = obj.verificar_limite()
        color = 'green'
        if estado['alcanzado_limite']:
            color = 'red'
        elif estado['alcanzado_80']:
            color = 'orange'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} / {}</span>',
            color,
            estado['documentos_usados'],
            estado['limite_documentos']
        )
    documentos_usados_display.short_description = 'Documentos (Usados/Límite)'
    
    def porcentaje_usado_display(self, obj):
        estado = obj.verificar_limite()
        porcentaje = estado['porcentaje_usado']
        
        # Determinar color de la barra
        if porcentaje >= 100:
            color = '#dc3545'  # Rojo
        elif porcentaje >= 80:
            color = '#fd7e14'  # Naranja
        elif porcentaje >= 50:
            color = '#ffc107'  # Amarillo
        else:
            color = '#28a745'  # Verde
        
        return format_html(
            '''
            <div style="width: 100px;">
                <div style="background-color: #e9ecef; border-radius: 4px; overflow: hidden;">
                    <div style="background-color: {}; width: {}%; height: 20px; text-align: center; line-height: 20px; color: white; font-size: 11px; font-weight: bold;">
                        {:.0f}%
                    </div>
                </div>
            </div>
            ''',
            color,
            min(porcentaje, 100),
            porcentaje
        )
    porcentaje_usado_display.short_description = 'Uso del Plan'
    
    def periodo_display(self, obj):
        dias = obj.dias_restantes
        if obj.periodo_vencido:
            return format_html('<span style="color: red;">⚠️ Vencido</span>')
        elif dias <= 7:
            return format_html('<span style="color: orange;">⏰ {} días</span>', dias)
        else:
            return format_html('<span style="color: green;">✓ {} días</span>', dias)
    periodo_display.short_description = 'Periodo'
    
    def estado_display(self, obj):
        estado = obj.verificar_limite()
        if not obj.activo:
            return format_html('<span style="color: gray;">❌ Inactivo</span>')
        elif estado['alcanzado_limite']:
            return format_html('<span style="color: red;">🚫 Límite Alcanzado</span>')
        elif estado['alcanzado_80']:
            return format_html('<span style="color: orange;">⚠️ Cerca del Límite</span>')
        else:
            return format_html('<span style="color: green;">✅ Activo</span>')
    estado_display.short_description = 'Estado'
    
    def acciones(self, obj):
        return format_html(
            '<a class="button" href="{}">Resetear</a>',
            reverse('admin:inventario_empresaplan_change', args=[obj.pk])
        )
    acciones.short_description = 'Acciones'
    
    def estadisticas_display(self, obj):
        if not obj.pk:
            return '-'
        
        estado = obj.verificar_limite()
        return format_html(
            '''
            <div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
                <p><strong>Documentos Restantes:</strong> {}</p>
                <p><strong>Porcentaje Usado:</strong> {:.2f}%</p>
                <p><strong>Estado:</strong> {}</p>
            </div>
            ''',
            estado['documentos_restantes'],
            estado['porcentaje_usado'],
            '✅ Puede autorizar' if estado['puede_autorizar'] else '🚫 Límite alcanzado'
        )
    estadisticas_display.short_description = 'Estadísticas de Uso'
    
    def periodo_info_display(self, obj):
        if not obj.pk:
            return '-'
        
        return format_html(
            '''
            <div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
                <p><strong>Inicio:</strong> {}</p>
                <p><strong>Fin:</strong> {}</p>
                <p><strong>Días Restantes:</strong> {}</p>
                <p><strong>Periodo:</strong> {}</p>
            </div>
            ''',
            obj.fecha_inicio,
            obj.fecha_fin,
            obj.dias_restantes,
            '⚠️ Vencido' if obj.periodo_vencido else '✅ Vigente'
        )
    periodo_info_display.short_description = 'Información del Periodo'
    
    def resetear_contadores(self, request, queryset):
        """Acción para resetear contadores de planes seleccionados"""
        count = 0
        for empresa_plan in queryset:
            empresa_plan.resetear_contador()
            count += 1
        
        self.message_user(
            request,
            f'Se resetearon {count} contadores exitosamente.'
        )
    resetear_contadores.short_description = 'Resetear contadores de planes seleccionados'
    
    def enviar_notificaciones(self, request, queryset):
        """Marcar como que se enviaron notificaciones"""
        queryset.update(notificacion_enviada=True)
        self.message_user(request, 'Notificaciones marcadas como enviadas.')
    enviar_notificaciones.short_description = 'Marcar notificaciones como enviadas'


@admin.register(HistorialPlan)
class HistorialPlanAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'plan', 'fecha_inicio', 'fecha_fin', 'documentos_autorizados']
    list_filter = ['plan', 'fecha_inicio']
    search_fields = ['empresa__razon_social', 'empresa__ruc']
    readonly_fields = ['creado_en']
    date_hierarchy = 'fecha_inicio'
    
    fieldsets = (
        ('Información', {
            'fields': ('empresa', 'plan')
        }),
        ('Periodo', {
            'fields': ('fecha_inicio', 'fecha_fin', 'documentos_autorizados')
        }),
        ('Detalles', {
            'fields': ('observaciones', 'creado_en')
        }),
    )
