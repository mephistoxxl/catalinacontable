"""Vistas para gestionar liquidaciones de compra (codDoc 03)."""
from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView

from ..mixins import RequireEmpresaActivaMixin, get_empresa_activa
from .forms import (
    CampoAdicionalFormSet,
    DetalleFormSet,
    FormaPagoFormSet,
    LiquidacionCompraForm,
)
from .models import LiquidacionCompra


class LiquidacionCompraListView(LoginRequiredMixin, RequireEmpresaActivaMixin, ListView):
    model = LiquidacionCompra
    template_name = "inventario/liquidacion_compra/listar.html"
    context_object_name = "liquidaciones"
    paginate_by = 25

    def get_queryset(self):
        empresa = get_empresa_activa(self.request)
        queryset = LiquidacionCompra.objects.none()
        if empresa:
            queryset = LiquidacionCompra.objects.filter(empresa=empresa).select_related("proveedor")
        return queryset.order_by("-fecha_emision", "-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = _("Liquidaciones de Compra")
        return context


class LiquidacionCompraCreateView(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    template_name = "inventario/liquidacion_compra/crear.html"
    success_url = reverse_lazy("inventario:liquidaciones_compra_listar")

    def _build_context(
        self,
        request,
        form=None,
        detalles=None,
        pagos=None,
        adicionales=None,
        productos_json="[]",
    ):
        empresa = get_empresa_activa(request)
        return {
            "form": form or LiquidacionCompraForm(empresa=empresa),
            "detalle_formset": detalles or DetalleFormSet(prefix="detalles"),
            "pago_formset": pagos or FormaPagoFormSet(prefix="pagos"),
            "campo_adicional_formset": adicionales or CampoAdicionalFormSet(prefix="adicionales"),
            "titulo": _("Nueva Liquidación de Compra"),
            "productos_json": productos_json,
        }

    def get(self, request, *args, **kwargs):
        context = self._build_context(request, productos_json="[]")
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        empresa = get_empresa_activa(request)
        if not empresa:
            messages.error(request, _("Debe seleccionar una empresa para continuar."))
            return redirect("inventario:seleccionar_empresa")

        form = LiquidacionCompraForm(request.POST, empresa=empresa)
        detalle_formset = DetalleFormSet(request.POST, prefix="detalles")
        pago_formset = FormaPagoFormSet(request.POST, prefix="pagos")
        adicional_formset = CampoAdicionalFormSet(request.POST, prefix="adicionales")

        if all([form.is_valid(), detalle_formset.is_valid(), pago_formset.is_valid(), adicional_formset.is_valid()]):
            with transaction.atomic():
                liquidacion = form.save(commit=False)
                liquidacion.empresa = empresa
                liquidacion.usuario_creacion = request.user
                liquidacion.estado = "BORRADOR"
                liquidacion.save()

                detalle_formset.instance = liquidacion
                detalle_formset.save()

                pago_formset.instance = liquidacion
                pago_formset.save()

                adicional_formset.instance = liquidacion
                adicional_formset.save()

                liquidacion.calcular_totales()
                liquidacion.sincronizar_formas_pago()
                liquidacion.save()

            messages.success(request, _("La liquidación se creó correctamente."))
            return redirect(self.success_url)

        messages.error(request, _("Por favor corrija los errores indicados."))
        productos_snapshot = request.POST.get("productos_snapshot", "[]")
        try:
            productos_json = json.dumps(json.loads(productos_snapshot))
        except json.JSONDecodeError:
            productos_json = "[]"

        context = self._build_context(
            request,
            form,
            detalle_formset,
            pago_formset,
            adicional_formset,
            productos_json=productos_json,
        )
        return render(request, self.template_name, context)
