from django.urls import path
from . import views

app_name = 'cxp'

urlpatterns = [
    path('', views.CuentaPagarListView.as_view(), name='lista_cuentas'),
    path('<int:pk>/', views.CuentaPagarDetailView.as_view(), name='detalle_cuenta'),
    path('<int:pk>/pago/nuevo/', views.RegistrarPagoView.as_view(), name='nuevo_pago'),
]