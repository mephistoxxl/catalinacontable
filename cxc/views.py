from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .models import CuentaCobrar, Abono

class CuentaCobrarListView(LoginRequiredMixin, ListView):
    model = CuentaCobrar
    template_name = 'cxc/lista_cxc.html'
    context_object_name = 'cuentas'

    def get_queryset(self):
        # Asumiendo que podemos obtener la empresa del request, de momento devolvemos todas o
        # las conectadas al usuario a través de alguna lógica.
        # Ajustaremos la lógica de filtrado de empresa cuando revisemos cómo lo hace inventario.
        return CuentaCobrar.objects.select_related('cliente', 'factura').all()

class CuentaCobrarDetailView(LoginRequiredMixin, DetailView):
    model = CuentaCobrar
    template_name = 'cxc/detalle_cxc.html'
    context_object_name = 'cuenta'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['abonos'] = self.object.abonos.all()
        return context

class RegistrarAbonoView(LoginRequiredMixin, CreateView):
    model = Abono
    fields = ['monto', 'metodo_pago', 'referencia_pago', 'observaciones']
    template_name = 'cxc/form_abono.html'

    def form_valid(self, form):
        cuenta = get_object_or_404(CuentaCobrar, pk=self.kwargs['pk'])
        form.instance.cuenta = cuenta
        form.instance.usuario = self.request.user
        messages.success(self.request, "Abono registrado correctamente.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('cxc:detalle_cuenta', kwargs={'pk': self.kwargs['pk']})
