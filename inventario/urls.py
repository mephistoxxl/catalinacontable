from django.urls import path, include, reverse_lazy
from . import views
from .views import FirmaElectronicaView, ConfiguracionGeneral
from .liquidacion_compra import views as liquidacion_views
from .nota_credito import views as nota_credito_views
from .nota_debito import views as nota_debito_views
from .retenciones import views as retencion_views
from .documentos_email import views as documentos_email_views
# TEMPORAL: Deshabilitado password reset por error en producción
# from .views_password_reset import SolicitarResetPassword, ResetPassword
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
app_name = "inventario"

urlpatterns = [
    # Login y Panel
    path('login', views.Login.as_view(), name='login'),
    path('seleccionar_empresa/', views.SeleccionarEmpresa.as_view(), name='seleccionar_empresa'),
    path('api/empresas/<str:identificacion>/', views.EmpresasPorUsuario.as_view(), name='empresas_por_usuario'),
    
    # Password Reset - TEMPORAL: Deshabilitado
    # path('solicitar-reset-password', SolicitarResetPassword.as_view(), name='solicitar_reset_password'),
    # path('reset-password/<str:token>/', ResetPassword.as_view(), name='reset_password'),
    
    path('panel', views.Panel.as_view(), name='panel'),
    path('reportes', views.Reportes.as_view(), name='reportes'),
    path('salir', views.Salir.as_view(), name='salir'),
    path('perfil/<str:modo>/<int:p>', views.Perfil.as_view(), name='perfil'),
    path('eliminar/<str:modo>/<int:p>', views.Eliminar.as_view(), name='eliminar'),

    # Productos
    path('listarProductos', views.ListarProductos.as_view(), name='listarProductos'),
    path('productos/exportar/', views.ExportarProductosExcel.as_view(), name='exportar_productos_excel'),
    path('productos/plantilla/', views.PlantillaProductosExcel.as_view(), name='plantilla_productos_excel'),
    path('agregarProducto', views.AgregarProducto.as_view(), name='agregarProducto'),
    path('importarProductos', views.ImportarProductos.as_view(), name='importarProductos'),
    path('exportarProductos', views.ExportarProductos.as_view(), name='exportarProductos'),
    path('editarProducto/<int:p>', views.EditarProducto.as_view(), name='editarProducto'),

    # Proveedores
    path('listarProveedores', views.ListarProveedores.as_view(), name='listarProveedores'),
    path('agregarProveedor', views.AgregarProveedor.as_view(), name='agregarProveedor'),
    path('importarProveedores', views.ImportarProveedores.as_view(), name='importarProveedores'),
    path('exportarProveedores', views.ExportarProveedores.as_view(), name='exportarProveedores'),
    path('editarProveedor/<int:p>', views.EditarProveedor.as_view(), name='editarProveedor'),

    # Pedidos
    path('agregarPedido', views.AgregarPedido.as_view(), name='agregarPedido'),
    path('listarPedidos', views.ListarPedidos.as_view(), name='listarPedidos'),
    path('detallesPedido', views.DetallesPedido.as_view(), name='detallesPedido'),
    path('verPedido/<int:p>', views.VerPedido.as_view(), name='verPedido'),
    path('validarPedido/<int:p>', views.ValidarPedido.as_view(), name='validarPedido'),
    path('generarPedido/<int:p>', views.GenerarPedido.as_view(), name='generarPedido'),
    path('generarPedidoPDF/<int:p>', views.GenerarPedidoPDF.as_view(), name='generarPedidoPDF'),

    # Clientes
    path('listarClientes', views.ListarClientes.as_view(), name='listarClientes'),
    path('agregarCliente', views.AgregarCliente.as_view(), name='agregarCliente'),
    path('importarClientes', views.ImportarClientes.as_view(), name='importarClientes'),
    path('exportarClientes', views.ExportarClientes.as_view(), name='exportarClientes'),
    path('editarCliente/<int:p>', views.EditarCliente.as_view(), name='editarCliente'),

    # Facturas
    path('emitirFactura', views.EmitirFactura.as_view(), name='emitirFactura'),
    path('detallesDeFactura', views.DetallesFactura.as_view(), name='detallesDeFactura'),
    path('listarFacturas', views.ListarFacturas.as_view(), name='listarFacturas'),
    path('verFactura/<int:p>', views.VerFactura.as_view(), name='verFactura'),
    path('verFactura/<int:p>/ticket', views.ImprimirFacturaTicket.as_view(), name='imprimir_factura_ticket'),
    path('editarFactura/<int:p>', views.EditarFactura.as_view(), name='editarFactura'),
    # path para autorizar documento movida a sección SRI (línea ~127)
    path('descargarRIDE/<int:p>/', views.VerFactura.as_view(), name='descargar_ride'),
    path('rideView/<int:p>/', views.RideView.as_view(), name='ride_view'),
    path('generarFactura/<int:p>', views.GenerarFactura.as_view(), name='generarFactura'),
    path('generarFacturaPDF/<int:p>', views.GenerarFacturaPDF.as_view(), name='generarFacturaPDF'),
    path('factura/<int:factura_id>/formas-pago/', views.FormasPagoView.as_view(), name='formasPago'),
    path('factura/<int:factura_id>/guardar-forma-pago/', views.GuardarFormaPagoView.as_view(), name='guardarFormaPago'),
    path('validar_facturador/', views.validar_facturador, name='validar_facturador'),
    path('facturas/<int:factura_id>/anular/', views.anular_factura, name='anular_factura'),

    # Proformas (placeholder views)
    path('proformas/', views.ListarProformas.as_view(), name='listarProformas'),
    path('proformas/emitir/', views.EmitirProforma.as_view(), name='emitirProforma'),
    path('proformas/ver/<int:p>/', views.VerProforma.as_view(), name='verProforma'),
    path('proformas/ride/<int:p>/', views.ride_proforma, name='ride_proforma'),
    path('proformas/imprimir/<int:p>/', views.imprimir_proforma, name='imprimir_proforma'),

    # Usuarios
    path('crearUsuario', views.CrearUsuario.as_view(), name='crearUsuario'),
    path('listarUsuarios', views.ListarUsuarios.as_view(), name='listarUsuarios'),

    # BDD y Configuración
    path('importarBDD', views.ImportarBDD.as_view(), name='importarBDD'),
    path('descargarBDD', views.DescargarBDD.as_view(), name='descargarBDD'),
    path('configuracionGeneral', ConfiguracionGeneral.as_view(), name='configuracionGeneral'),
    path('verManualDeUsuario/<str:pagina>/', views.VerManualDeUsuario.as_view(), name='verManualDeUsuario'),

    # Secuencias
    path('secuencias/', views.Secuencias.as_view(), name='secuencias'),
    path('secuencias/crear/', views.Secuencias.as_view(), name='crear_secuencia'),
    path('ListaSecuencias/', views.ListaSecuencias.as_view(), name='lista_secuencias'),
    path('editarSecuencia/<int:id>/', views.EditarSecuencia.as_view(), name='editar_secuencia'),
    path('eliminarSecuencia/<int:id>/', views.EliminarSecuencia.as_view(), name='eliminar_secuencia'),

    # Facturadores
    path('facturadores/', views.ListarFacturadores.as_view(), name='listar_facturadores'),
    path('facturadores/crear/', views.CrearFacturador.as_view(), name='crear_facturador'),
    path('facturadores/editar/<int:id>/', views.EditarFacturador.as_view(), name='editar_facturador'),
    path('facturadores/eliminar/<int:id>/', views.EliminarFacturador.as_view(), name='eliminar_facturador'),

    # Login para facturadores
    path('login_facturador/', views.LoginFacturador.as_view(), name='login_facturador'),

    # Login para proformadores
    path('login_proformador/', views.LoginProformador.as_view(), name='login_proformador'),

    # Búsqueda y Almacenes
    path('buscar_cliente/', views.buscar_cliente, name='buscar_cliente'),
    path('buscar_producto/', views.buscar_producto, name='buscar_producto'),
    path('almacenes/', views.gestion_almacenes, name='gestion_almacenes'),
    path('almacenes/editar/<int:id>/', views.editar_almacen, name='editar_almacen'),
    path('almacenes/eliminar/<int:id>/', views.eliminar_almacen, name='eliminar_almacen'),

    # Liquidaciones de compra (codDoc 03)
    path('liquidaciones-compra/', liquidacion_views.LiquidacionCompraListView.as_view(), name='liquidaciones_compra_listar'),
    path('liquidaciones-compra/crear/', liquidacion_views.LiquidacionCompraCreateView.as_view(), name='liquidaciones_compra_crear'),
    path('liquidaciones-compra/ver/<int:pk>/', liquidacion_views.LiquidacionCompraDetailView.as_view(), name='liquidaciones_compra_ver'),
    path('liquidaciones-compra/autorizar/<int:pk>/', liquidacion_views.autorizar_liquidacion_compra, name='autorizar_liquidacion_compra'),
    path('liquidaciones-compra/consultar-estado/<int:pk>/', liquidacion_views.consultar_estado_liquidacion_compra, name='consultar_estado_liquidacion_compra'),
    path('liquidaciones-compra/consultar-estado-json/<int:pk>/', liquidacion_views.consultar_estado_liquidacion_compra_json, name='consultar_estado_liquidacion_compra_json'),
    path('liquidaciones-compra/enviar-email/<int:pk>/', documentos_email_views.enviar_email_liquidacion, name='liquidaciones_compra_enviar_email'),

    # Retenciones (codDoc 07)
    path('retenciones/', retencion_views.ListarRetenciones.as_view(), name='retenciones_listar'),
    path('retenciones/crear/', retencion_views.CrearRetencion.as_view(), name='retenciones_crear'),
    path('retenciones/<int:pk>/editar/', retencion_views.EditarRetencion.as_view(), name='retenciones_editar'),
    path('retenciones/<int:pk>/xml/', retencion_views.DescargarXMLRetencion.as_view(), name='retenciones_xml'),
    path('retenciones/<int:pk>/xml-firmado/', retencion_views.DescargarXMLFirmadoRetencion.as_view(), name='retenciones_xml_firmado'),
    path('retenciones/<int:pk>/pdf/', retencion_views.DescargarPDFRetencion.as_view(), name='retenciones_pdf'),
    path('retenciones/<int:pk>/autorizar/', retencion_views.AutorizarRetencion.as_view(), name='retenciones_autorizar'),
    path('retenciones/<int:pk>/consultar-estado/', retencion_views.ConsultarEstadoRetencion.as_view(), name='retenciones_consultar_estado'),
    path('retenciones/<int:pk>/enviar-email/', documentos_email_views.enviar_email_retencion, name='retenciones_enviar_email'),

    # Notas de Crédito (codDoc 04)
    path('notas-credito/', nota_credito_views.ListarNotasCredito.as_view(), name='notas_credito_listar'),
    path('notas-credito/crear/', nota_credito_views.CrearNotaCredito.as_view(), name='notas_credito_crear'),
    path('notas-credito/crear/<int:factura_id>/', nota_credito_views.CrearNotaCredito.as_view(), name='notas_credito_crear_factura'),
    path('notas-credito/ver/<int:pk>/', nota_credito_views.VerNotaCredito.as_view(), name='notas_credito_ver'),
    path('notas-credito/autorizar/<int:pk>/', nota_credito_views.AutorizarNotaCredito.as_view(), name='notas_credito_autorizar'),
    path('notas-credito/consultar-estado/<int:pk>/', nota_credito_views.ConsultarEstadoNotaCredito.as_view(), name='notas_credito_consultar_estado'),
    path('notas-credito/pdf/<int:pk>/', nota_credito_views.DescargarPDF.as_view(), name='notas_credito_pdf'),
    path('notas-credito/enviar-email/<int:pk>/', documentos_email_views.enviar_email_nota_credito, name='notas_credito_enviar_email'),

    # Notas de Débito (codDoc 05)
    path('notas-debito/', nota_debito_views.ListarNotasDebito.as_view(), name='notas_debito_listar'),
    path('notas-debito/crear/', nota_debito_views.CrearNotaDebito.as_view(), name='notas_debito_crear'),
    path('notas-debito/crear/<int:factura_id>/', nota_debito_views.CrearNotaDebito.as_view(), name='notas_debito_crear_factura'),
    path('notas-debito/ver/<int:pk>/', nota_debito_views.VerNotaDebito.as_view(), name='notas_debito_ver'),
    path('notas-debito/autorizar/<int:pk>/', nota_debito_views.AutorizarNotaDebito.as_view(), name='notas_debito_autorizar'),
    path('notas-debito/consultar-estado/<int:pk>/', nota_debito_views.ConsultarEstadoNotaDebito.as_view(), name='notas_debito_consultar_estado'),
    path('notas-debito/pdf/<int:pk>/', nota_debito_views.DescargarPDFNotaDebito.as_view(), name='notas_debito_pdf'),
    path('notas-debito/enviar-email/<int:pk>/', documentos_email_views.enviar_email_nota_debito, name='notas_debito_enviar_email'),

    # Bancos
    path('bancos/', views.ListarBancos.as_view(), name='listar_bancos'),
    path('bancos/crear/', views.CrearBanco.as_view(), name='crear_banco'),
    path('bancos/editar/<int:id>/', views.EditarBanco.as_view(), name='editar_banco'),
    path('bancos/ver/<int:id>/', views.VerBanco.as_view(), name='ver_banco'),
    path('bancos/eliminar/<int:id>/', views.EliminarBanco.as_view(), name='eliminar_banco'),

    # Cajas
    path('cajas/', views.ListarCajas.as_view(), name='listarCajas'),
    path('cajas/agregar/', views.AgregarCaja.as_view(), name='agregarCaja'),
    path('cajas/editar/<int:id>/', views.EditarCaja.as_view(), name='editarCaja'),
    path('cajas/ver/<int:id>/', views.VerCaja.as_view(), name='verCaja'),
    path('cajas/eliminar/<int:id>/', views.EliminarCaja.as_view(), name='eliminarCaja'),

    # Otros
    path('obtener_datos_secuencia/<int:secuencia_id>/', views.obtener_datos_secuencia, name='obtener_datos_secuencia'),

    # Consultar identificación (RUC o cédula)
    path('consultar-identificacion/', views.consultar_identificacion, name='consultar_identificacion'),
    path('guardar_cliente_automatico/', views.guardar_cliente_automatico, name='guardar_cliente_automatico'),

    # Firma Electrónica
    path('configuracion/firma-electronica/', FirmaElectronicaView.as_view(), name='firma_electronica'),
    path('configuracion/firma-electronica/eliminar/', views.EliminarFirmaElectronicaView.as_view(), name='eliminar_firma_electronica'),
    path('configuracion/firma-electronica/descargar/', views.DescargarFirmaElectronicaView.as_view(), name='descargar_firma_electronica'),

    # Servicios
    path('listarServicios', views.ListarServicios.as_view(), name='listarServicios'),
    path('agregarServicio', views.AgregarServicio.as_view(), name='agregarServicio'),
    path('editarServicio/<int:p>', views.EditarServicio.as_view(), name='editarServicio'),
    path('eliminarServicio/<int:p>', views.EliminarServicio.as_view(), name='eliminarServicio'),

    #para consultar RUC empresa
    path('buscar_empresa/', views.buscar_empresa, name='buscar_empresa'),
    path('api/empresa/<str:ruc>/', views.empresa_api, name='empresa_api'),

    # ✅ NUEVAS URLs PARA INTEGRACIÓN SRI COMPLETA
    path('sri/enviar/<int:factura_id>/', views.enviar_documento_sri, name='enviar_documento_sri'),
    path('sri/enviar-bg/<int:factura_id>/', views.enviar_documento_sri_background, name='enviar_documento_sri_background'),
    path('sri/autorizar/<int:factura_id>/', views.autorizar_documento_sri, name='autorizar_documento_sri'),
    path('sri/consultar/<int:factura_id>/', views.consultar_estado_sri, name='consultar_estado_sri'),
    path('sri/enviar-email/<int:factura_id>/', views.enviar_factura_email, name='enviar_factura_email'),
    path('sri/reenviar/<int:factura_id>/', views.reenviar_factura_sri, name='reenviar_factura_sri'),
    path('sri/xml/<int:factura_id>/', views.generar_xml_factura_view, name='generar_xml_factura'),
    path('sri/problemas/', views.FacturasSRIProblemas.as_view(), name='facturas_sri_problemas'),
    path('sri/sincronizar-masivo/', views.sincronizar_masivo_sri, name='sincronizar_masivo_sri'),
    path('sri/validar-xml/<int:factura_id>/', views.validar_xml_factura, name='validar_xml_factura'),

    # Vista de debug temporal para proformas
    path('debug/proforma-data/', views.debug_proforma_data, name='debug_proforma_data'),

    # Guías de Remisión
    path('guias-remision/', views.listar_guias_remision, name='listar_guias_remision'),
    path('guias-remision/emitir/', views.emitir_guia_remision, name='emitir_guia_remision'),
    path('obtener_datos_factura/<int:factura_id>/', views.obtener_datos_factura, name='obtener_datos_factura'),
    path('guias-remision/<int:guia_id>/', views.ver_guia_remision, name='ver_guia_remision'),
    path('guias-remision/<int:guia_id>/estado-json/', views.consultar_estado_guia_remision_json, name='consultar_estado_guia_remision_json'),
    path('guias-remision/<int:guia_id>/editar/', views.editar_guia_remision, name='editar_guia_remision'),
    path('guias-remision/<int:guia_id>/autorizar/', views.autorizar_guia_remision, name='autorizar_guia_remision'),
    path('guias-remision/<int:guia_id>/anular/', views.anular_guia_remision, name='anular_guia_remision'),
    path('guias-remision/<int:guia_id>/pdf/', views.descargar_guia_pdf, name='descargar_guia_pdf'),
    path('guias-remision/<int:guia_id>/xml/', views.descargar_guia_xml, name='descargar_guia_xml'),
    path('guias-remision/<int:guia_id>/enviar-email/', documentos_email_views.enviar_email_guia, name='guias_remision_enviar_email'),
    path('api/buscar-transportista/', views.buscar_transportista, name='buscar_transportista'),
    path('api/buscar-cliente/', views.buscar_cliente_ajax, name='buscar_cliente_ajax'),
    path('api/clientes/buscar', views.buscar_cliente_api, name='buscar_cliente_api'),
    path('api/clientes/crear', views.crear_cliente_api, name='crear_cliente_api'),
    path('api/clientes/actualizar', views.actualizar_cliente_api, name='actualizar_cliente_api'),
    path('api/clientes/enriquecer', views.enriquecer_cliente_api, name='enriquecer_cliente_api'),
    path('api/verificar-limite-plan/', views.api_verificar_limite, name='api_verificar_limite_plan'),

    # Restablecimiento de contraseña para nuevos usuarios
    path(
        'cuentas/restablecer/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='inventario/usuario/password_reset_confirm.html',
            success_url=reverse_lazy('inventario:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'cuentas/restablecer/completo/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='inventario/usuario/password_reset_complete.html',
            extra_context={'login_url': reverse_lazy('inventario:login')},
        ),
        name='password_reset_complete',
    ),
]

# Servir archivos de medios en desarrollo
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)