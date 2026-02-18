from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from ..mixins import RequireEmpresaActivaMixin, get_empresa_activa
from ..models import Secuencia
from .forms import RetencionCampoAdicionalFormSet, RetencionCompraForm, RetencionImpuestoFormSet
from .integracion_sri_retencion import IntegracionSRIRetencion
from .models import RetencionCompra


class RetencionCompraListView(LoginRequiredMixin, RequireEmpresaActivaMixin, ListView):
    model = RetencionCompra
    template_name = "inventario/retenciones/listar.html"
    context_object_name = "retenciones"
    paginate_by = 10

    def get_queryset(self):
        empresa = get_empresa_activa(self.request)
        qs = RetencionCompra.objects.none()
        if empresa:
            qs = RetencionCompra.objects.filter(empresa=empresa).select_related("proveedor")
        return qs.order_by("-fecha_emision", "-id")


class RetencionCompraCreateView(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    template_name = "inventario/retenciones/crear.html"
    SECUENCIA_TIPO_DOCUMENTO = "07"

    def _calcular_datos_secuencia(self, empresa, secuencia):
        if not empresa or not secuencia:
            return None

        max_existente = RetencionCompra.objects.filter(
            empresa=empresa,
            establecimiento=secuencia.establecimiento,
            punto_emision=secuencia.punto_emision,
        ).aggregate(m=Max("secuencia"))["m"] or 0

        base = int(secuencia.secuencial or 0)
        siguiente = max(max_existente + 1, base or 1)

        while RetencionCompra.objects.filter(
            empresa=empresa,
            establecimiento=secuencia.establecimiento,
            punto_emision=secuencia.punto_emision,
            secuencia=siguiente,
        ).exists():
            siguiente += 1

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

    def get(self, request, *args, **kwargs):
        empresa = get_empresa_activa(request)
        secuencia_info = self._obtener_siguiente_secuencia(empresa)
        initial = {
            "fecha_emision": timezone.localdate(),
            "fecha_emision_doc_sustento": timezone.localdate(),
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

        context = {
            "form": RetencionCompraForm(empresa=empresa, initial=initial),
            "impuesto_formset": RetencionImpuestoFormSet(prefix="impuestos"),
            "campo_adicional_formset": RetencionCampoAdicionalFormSet(prefix="adicionales"),
            "secuencia_info": secuencia_info,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        empresa = get_empresa_activa(request)
        if not empresa:
            messages.error(request, "Debe seleccionar una empresa activa.")
            return redirect("inventario:seleccionar_empresa")

        form = RetencionCompraForm(request.POST, empresa=empresa)
        impuesto_formset = RetencionImpuestoFormSet(request.POST, prefix="impuestos")
        adicional_formset = RetencionCampoAdicionalFormSet(request.POST, prefix="adicionales")

        if form.is_valid() and impuesto_formset.is_valid() and adicional_formset.is_valid():
            try:
                with transaction.atomic():
                    secuencia_info = self._obtener_siguiente_secuencia(
                        empresa,
                        form.cleaned_data.get("secuencia_config_id"),
                        lock=True,
                    )
                    if not secuencia_info:
                        raise Secuencia.DoesNotExist

                    retencion = form.save(commit=False)
                    retencion.empresa = empresa
                    retencion.usuario_creacion = request.user
                    retencion.establecimiento = secuencia_info["establecimiento"]
                    retencion.punto_emision = secuencia_info["punto_emision"]
                    retencion.secuencia = secuencia_info["valor"]
                    retencion.estado = "BORRADOR"
                    retencion.save()

                    secuencia_obj = secuencia_info["secuencia"]
                    if secuencia_obj.secuencial != secuencia_info["valor"]:
                        secuencia_obj.secuencial = secuencia_info["valor"]
                        secuencia_obj.save(update_fields=["secuencial"])

                    impuesto_formset.instance = retencion
                    impuesto_formset.save()

                    adicional_formset.instance = retencion
                    adicional_formset.save()

                    retencion.calcular_totales()
                    retencion.save(update_fields=["total_retenido_renta", "total_retenido_iva", "total_retenido", "actualizado_en"])

                messages.success(request, "Retención creada correctamente.")
                return redirect("inventario:retenciones_compra_ver", pk=retencion.pk)
            except Secuencia.DoesNotExist:
                messages.error(request, "No existe una secuencia activa para tipo de documento 07.")
            except Exception as exc:
                messages.error(request, f"No se pudo crear la retención: {exc}")

        messages.error(request, "Corrija los errores del formulario.")
        context = {
            "form": form,
            "impuesto_formset": impuesto_formset,
            "campo_adicional_formset": adicional_formset,
            "secuencia_info": self._obtener_siguiente_secuencia(empresa, form.data.get("secuencia_config_id")),
        }
        return render(request, self.template_name, context)


class RetencionCompraDetailView(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    template_name = "inventario/retenciones/ver.html"

    def get(self, request, pk, *args, **kwargs):
        empresa = get_empresa_activa(request)
        retencion = get_object_or_404(
            RetencionCompra.objects.select_related("proveedor", "empresa", "usuario_creacion").prefetch_related(
                "impuestos",
                "campos_adicionales",
                "historial_estados",
            ),
            pk=pk,
            empresa=empresa,
        )
        return render(request, self.template_name, {"retencion": retencion})


@login_required
def autorizar_retencion_compra(request, pk):
    empresa = get_empresa_activa(request)
    if not empresa:
        messages.error(request, "Seleccione una empresa activa.")
        return redirect("inventario:seleccionar_empresa")

    retencion = get_object_or_404(RetencionCompra, pk=pk, empresa=empresa)

    try:
        integracion = IntegracionSRIRetencion(empresa)
        resultado = integracion.procesar_retencion_completa(retencion)
        if resultado.get("exito"):
            messages.success(request, "Retención procesada con éxito en SRI.")
        else:
            mensajes = resultado.get("mensajes", []) or [resultado.get("estado", "Error")]
            for msg in mensajes:
                if isinstance(msg, dict):
                    messages.error(request, msg.get("mensaje") or str(msg))
                else:
                    messages.error(request, str(msg))
    except Exception as exc:
        messages.error(request, f"Error al procesar retención: {exc}")

    return redirect("inventario:retenciones_compra_ver", pk=retencion.pk)


@login_required
def consultar_estado_retencion_compra(request, pk):
    empresa = get_empresa_activa(request)
    if not empresa:
        messages.error(request, "Seleccione una empresa activa.")
        return redirect("inventario:seleccionar_empresa")

    retencion = get_object_or_404(RetencionCompra, pk=pk, empresa=empresa)

    try:
        integracion = IntegracionSRIRetencion(empresa)
        resultado = integracion.consultar_estado_actual(retencion)
        if resultado.get("exito"):
            messages.success(request, "Estado SRI actualizado.")
        else:
            messages.info(request, (resultado.get("estado") or "PENDIENTE"))
    except Exception as exc:
        messages.error(request, f"No se pudo consultar estado SRI: {exc}")

    return redirect("inventario:retenciones_compra_ver", pk=retencion.pk)


@login_required
def consultar_estado_retencion_compra_json(request, pk):
    empresa = get_empresa_activa(request)
    if not empresa:
        return JsonResponse({"success": False, "message": "Seleccione empresa."}, status=400)

    retencion = get_object_or_404(RetencionCompra, pk=pk, empresa=empresa)

    try:
        integracion = IntegracionSRIRetencion(empresa)
        resultado = integracion.consultar_estado_actual(retencion)
        retencion.refresh_from_db()

        return JsonResponse(
            {
                "success": bool(resultado.get("exito")),
                "estado": retencion.estado_sri or resultado.get("estado") or "PENDIENTE",
                "mensaje": resultado.get("mensajes", ["Consulta realizada"])[0]
                if resultado.get("mensajes")
                else "Consulta realizada",
                "numero_autorizacion": retencion.numero_autorizacion or "",
                "fecha_autorizacion": retencion.fecha_autorizacion.strftime("%d/%m/%Y %H:%M:%S")
                if retencion.fecha_autorizacion
                else "",
            }
        )
    except Exception as exc:
        return JsonResponse({"success": False, "estado": "ERROR", "message": str(exc)}, status=500)
