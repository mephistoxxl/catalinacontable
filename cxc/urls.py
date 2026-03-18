from django.urls import path
from . import views

app_name = 'cxc'

urlpatterns = [
    path('', views.CuentaCobrarListView.as_view(), name='lista_cuentas'),
    path('<int:pk>/', views.CuentaCobrarDetailView.as_view(), name='detalle_cuenta'),
    path('<int:pk>/abono/nuevo/', views.RegistrarAbonoView.as_view(), name='nuevo_abono'),
]
