from django.urls import path
from . import views

# URLs para el módulo de Guías de Remisión
urlpatterns = [
    # Listado y vista principal
    path('guias-remision/', views.listar_guias_remision, name='listar_guias_remision'),
    
    # CRUD de guías
    path('guias-remision/emitir/', views.emitir_guia_remision, name='emitir_guia_remision'),
    path('guias-remision/<int:guia_id>/', views.ver_guia_remision, name='ver_guia_remision'),
    path('guias-remision/<int:guia_id>/editar/', views.editar_guia_remision, name='editar_guia_remision'),
    path('guias-remision/<int:guia_id>/anular/', views.anular_guia_remision, name='anular_guia_remision'),
    
    # Descarga de archivos
    path('guias-remision/<int:guia_id>/pdf/', views.descargar_guia_pdf, name='descargar_guia_pdf'),
    
    # AJAX endpoints
    path('api/buscar-cliente/', views.buscar_cliente_ajax, name='buscar_cliente_ajax'),
]
