"""Vistas para gestionar liquidaciones de compra (codDoc 03)."""
from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Max
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from ..mixins import RequireEmpresaActivaMixin, get_empresa_activa
from ..models import Secuencia
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
    SECUENCIA_TIPO_DOCUMENTO = "03"

    def _calcular_datos_secuencia(self, empresa, secuencia):
        if not empresa or not secuencia:
            return None

        max_existente = LiquidacionCompra.objects.filter(
            empresa=empresa,
            establecimiento=secuencia.establecimiento,
            punto_emision=secuencia.punto_emision,
        ).aggregate(m=Max("secuencia"))["m"] or 0

        base = secuencia.secuencial or 0
        if max_existente > 0:
            siguiente = max_existente + 1
        else:
            siguiente = max(base, 1)
        if siguiente > 999_999_999:
            raise ValueError("El secuencial ha alcanzado el valor máximo permitido (999999999).")

        return {
            "secuencia": secuencia,
            "establecimiento": secuencia.establecimiento,
            "punto_emision": secuencia.punto_emision,
            "valor": siguiente,
            "establecimiento_str": f"{secuencia.establecimiento:03d}",
            "punto_emision_str": f"{secuencia.punto_emision:03d}",
            "valor_str": f"{siguiente:09d}",
        }

    def _obtener_siguiente_secuencia(self, empresa, secuencia_id=None, lock=False):
        if not empresa:
            return None

        qs = Secuencia.objects.filter(
            empresa=empresa,
            tipo_documento=self.SECUENCIA_TIPO_DOCUMENTO,
            activo=True,
        )
        if secuencia_id:
            qs = qs.filter(id=secuencia_id)
        if lock:
            qs = qs.select_for_update()

        secuencia = qs.order_by("establecimiento", "punto_emision").first()
        if not secuencia:
            return None

        return self._calcular_datos_secuencia(empresa, secuencia)

    def _build_context(
        self,
        request,
        form=None,
        detalles=None,
        pagos=None,
        adicionales=None,
        productos_json="[]",
        secuencia_info=None,
    ):
        empresa = get_empresa_activa(request)
        return {
            "form": form or LiquidacionCompraForm(empresa=empresa),
            "detalle_formset": detalles or DetalleFormSet(prefix="detalles"),
            "pago_formset": pagos or FormaPagoFormSet(prefix="pagos"),
            "campo_adicional_formset": adicionales or CampoAdicionalFormSet(prefix="adicionales"),
            "titulo": _("Nueva Liquidación de Compra"),
            "productos_json": productos_json,
            "secuencia_info": secuencia_info,
        }

    def get(self, request, *args, **kwargs):
        empresa = get_empresa_activa(request)
        secuencia_info = self._obtener_siguiente_secuencia(empresa)
        initial = {
            "fecha_emision": timezone.localdate(),
        }
        if secuencia_info:
            initial.update(
                {
                    "establecimiento": secuencia_info["establecimiento_str"],
                    "punto_emision": secuencia_info["punto_emision_str"],
                    "secuencia": secuencia_info["valor_str"],
                    "secuencia_config_id": secuencia_info["secuencia"].id,
                }
            )

        form = LiquidacionCompraForm(empresa=empresa, initial=initial)
        context = self._build_context(request, form=form, productos_json="[]", secuencia_info=secuencia_info)
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
            try:
                with transaction.atomic():
                    secuencia_info = self._obtener_siguiente_secuencia(
                        empresa,
                        form.cleaned_data.get("secuencia_config_id"),
                        lock=True,
                    )
                    if not secuencia_info:
                        raise Secuencia.DoesNotExist

                    liquidacion = form.save(commit=False)
                    liquidacion.empresa = empresa
                    liquidacion.usuario_creacion = request.user
                    liquidacion.estado = "BORRADOR"
                    liquidacion.establecimiento = secuencia_info["establecimiento"]
                    liquidacion.punto_emision = secuencia_info["punto_emision"]
                    liquidacion.secuencia = secuencia_info["valor"]
                    liquidacion.save()

                    # Actualizar el secuencial en la configuración utilizada
                    secuencia_obj = secuencia_info["secuencia"]
                    if secuencia_obj.secuencial != secuencia_info["valor"]:
                        secuencia_obj.secuencial = secuencia_info["valor"]
                        secuencia_obj.save(update_fields=["secuencial"])

                    form.guardar_prestador(liquidacion)

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
            except Secuencia.DoesNotExist:
                messages.error(
                    request,
                    _("No se encontró una secuencia activa para liquidaciones de compra. Configure una antes de continuar."),
                )
            except ValueError as error:
                form.add_error(None, str(error))

        messages.error(request, _("Por favor corrija los errores indicados."))
        productos_snapshot = request.POST.get("productos_snapshot", "[]")
        try:
            productos_json = json.dumps(json.loads(productos_snapshot))
        except json.JSONDecodeError:
            productos_json = "[]"

        secuencia_info = self._obtener_siguiente_secuencia(empresa, form.cleaned_data.get("secuencia_config_id"))
        context = self._build_context(
            request,
            form,
            detalle_formset,
            pago_formset,
            adicional_formset,
            productos_json=productos_json,
            secuencia_info=secuencia_info,
        )
        return render(request, self.template_name, context)
