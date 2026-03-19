from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import CuentaPagar, PagoProveedor
from inventario.mixins import get_empresa_activa

class CuentaPagarListView(LoginRequiredMixin, ListView):
    model = CuentaPagar
    template_name = 'cxp/lista_cxp.html'
    context_object_name = 'cuentas'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = CuentaPagar.objects.select_related('proveedor').all()

        empresa_activa = get_empresa_activa(self.request)
        if empresa_activa:
            return qs.filter(empresa=empresa_activa).order_by('fecha_vencimiento')
        
        # Filtrar por empresas del usuario si tiene el atributo empresas
        if hasattr(user, 'empresas') and user.empresas.exists():
            qs = qs.filter(empresa__in=user.empresas.all())
        elif hasattr(user, 'empresa') and user.empresa:
             qs = qs.filter(empresa=user.empresa)
            
        return qs.order_by('fecha_vencimiento')

class CuentaPagarDetailView(LoginRequiredMixin, DetailView):
    model = CuentaPagar
    template_name = 'cxp/detalle_cxp.html'
    context_object_name = 'cuenta'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pagos'] = self.object.pagos.all().order_by('-fecha_pago')
        return context

class RegistrarPagoView(LoginRequiredMixin, CreateView):
    model = PagoProveedor
    fields = ['monto', 'metodo_pago', 'referencia_pago', 'observaciones', 'fecha_pago']
    template_name = 'cxp/form_pago.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cuenta'] = get_object_or_404(CuentaPagar, pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        cuenta = get_object_or_404(CuentaPagar, pk=self.kwargs['pk'])
        
        # Validar que el monto no exceda el saldo
        if form.cleaned_data['monto'] > cuenta.saldo_pendiente:
            form.add_error('monto', f"El monto no puede exceder el saldo pendiente (${cuenta.saldo_pendiente})")
            return self.form_invalid(form)

        form.instance.cuenta = cuenta
        form.instance.usuario = self.request.user
        messages.success(self.request, "Pago registrado correctamente.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('cxp:detalle_cuenta', kwargs={'pk': self.kwargs['pk']})