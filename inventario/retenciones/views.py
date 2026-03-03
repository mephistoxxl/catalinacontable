from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from ..mixins import RequireEmpresaActivaMixin, get_empresa_activa
from ..models import Secuencia
from .forms import ComprobanteRetencionForm
from .models import ComprobanteRetencion, RetencionDetalle
from .services import (
    calcular_valor_retenido,
    porcentaje_iva_por_codigo,
    porcentaje_renta_sugerido,
)
from .xml_generator_retencion import RetencionXMLGenerator


class ListarRetenciones(LoginRequiredMixin, RequireEmpresaActivaMixin, ListView):
    login_url = '/inventario/login'
    template_name = 'inventario/retencion/listar.html'
    context_object_name = 'retenciones'
    paginate_by = 20

    def get_queryset(self):
        empresa = get_empresa_activa(self.request)
        if not empresa:
            return ComprobanteRetencion.objects.none()

        queryset = ComprobanteRetencion.objects.filter(empresa=empresa).order_by('-fecha_emision_retencion', '-id')

        q = (self.request.GET.get('q') or '').strip()
        if q:
            queryset = queryset.filter(
                Q(razon_social_sujeto__icontains=q)
                | Q(identificacion_sujeto__icontains=q)
                | Q(secuencia_retencion__icontains=q)
            )

        estado = (self.request.GET.get('estado') or '').strip()
        if estado:
            queryset = queryset.filter(estado_sri=estado)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Retenciones'
        context['menu_actual'] = 'compras'
        context['opcion_actual'] = 'listar_retenciones'
        return context


class CrearRetencion(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'
    template_name = 'inventario/retencion/crear.html'
    SECUENCIA_TIPO_DOCUMENTO = '07'

    def _obtener_siguiente_secuencia(self, empresa):
        secuencia_cfg = (
            Secuencia.objects.filter(
                empresa=empresa,
                tipo_documento=self.SECUENCIA_TIPO_DOCUMENTO,
                activo=True,
            )
            .order_by('establecimiento', 'punto_emision')
            .first()
        )

        establecimiento = f"{(secuencia_cfg.establecimiento if secuencia_cfg else 1):03d}"
        punto = f"{(secuencia_cfg.punto_emision if secuencia_cfg else 901):03d}"

        max_existente = (
            ComprobanteRetencion.objects.filter(
                empresa=empresa,
                establecimiento_retencion=establecimiento,
                punto_emision_retencion=punto,
            ).aggregate(m=Max('secuencia_retencion'))['m']
            or '000000000'
        )

        try:
            max_valor = int(max_existente)
        except (TypeError, ValueError):
            max_valor = 0

        base_cfg = 1
        if secuencia_cfg:
            try:
                base_cfg = int(secuencia_cfg.secuencial or 1)
            except (TypeError, ValueError):
                base_cfg = 1

        siguiente = max(max_valor + 1, base_cfg)
        return {
            'config': secuencia_cfg,
            'establecimiento': establecimiento,
            'punto_emision': punto,
            'secuencia': f'{siguiente:09d}',
            'secuencia_int': siguiente,
        }

    def get(self, request, *args, **kwargs):
        empresa = get_empresa_activa(request)
        secuencia_info = self._obtener_siguiente_secuencia(empresa)
        form = ComprobanteRetencionForm(
            initial={
                'establecimiento_retencion': secuencia_info['establecimiento'],
                'punto_emision_retencion': secuencia_info['punto_emision'],
                'secuencia_retencion': secuencia_info['secuencia'],
            }
        )
        return render(
            request,
            self.template_name,
            {
                'form': form,
                'titulo': 'Emitir Retención',
                'menu_actual': 'compras',
                'opcion_actual': 'emitir_retencion',
            },
        )

    def post(self, request, *args, **kwargs):
        empresa = get_empresa_activa(request)
        form = ComprobanteRetencionForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Por favor corrige los campos del formulario de retención.')
            return render(
                request,
                self.template_name,
                {
                    'form': form,
                    'titulo': 'Emitir Retención',
                    'menu_actual': 'compras',
                    'opcion_actual': 'emitir_retencion',
                },
            )

        with transaction.atomic():
            retencion = form.save(commit=False)
            retencion.empresa = empresa
            retencion.usuario_creacion = request.user
            retencion.limpiar_estado_xml()
            retencion.save()

            renta_base = form.cleaned_data.get('renta_base') or Decimal('0.00')
            renta_codigo = (form.cleaned_data.get('codigo_renta') or '304B').strip()
            renta_porcentaje = form.cleaned_data.get('renta_porcentaje') or Decimal('0.00')
            if renta_porcentaje <= 0:
                renta_porcentaje = porcentaje_renta_sugerido(renta_codigo)
            if renta_base > 0 and renta_porcentaje > 0:
                RetencionDetalle.objects.create(
                    comprobante=retencion,
                    tipo_impuesto='RENTA',
                    codigo_retencion=renta_codigo,
                    descripcion_retencion='Retención Renta',
                    base_imponible=renta_base,
                    porcentaje_retener=renta_porcentaje,
                    valor_retenido=calcular_valor_retenido(renta_base, renta_porcentaje),
                )

            iva_base = form.cleaned_data.get('iva_base') or Decimal('0.00')
            iva_codigo = (form.cleaned_data.get('codigo_iva') or '721').strip()
            iva_porcentaje = porcentaje_iva_por_codigo(iva_codigo)
            if iva_base > 0 and iva_porcentaje > 0:
                RetencionDetalle.objects.create(
                    comprobante=retencion,
                    tipo_impuesto='IVA',
                    codigo_retencion=iva_codigo,
                    descripcion_retencion='Retención IVA',
                    base_imponible=iva_base,
                    porcentaje_retener=iva_porcentaje,
                    valor_retenido=calcular_valor_retenido(iva_base, iva_porcentaje),
                )

            retencion.recalcular_totales()

            xml_gen = RetencionXMLGenerator(retencion)
            retencion.clave_acceso = xml_gen.generar_clave_acceso()
            retencion.xml_generado = xml_gen.generar_xml()
            validacion = xml_gen.validar_xml(retencion.xml_generado)
            retencion.xml_validado = validacion.valido
            retencion.xml_validacion_error = '' if validacion.valido else (validacion.errores or validacion.mensaje)

            retencion.save(
                update_fields=[
                    'total_retencion_renta',
                    'total_retencion_iva',
                    'total_retenido',
                    'clave_acceso',
                    'xml_generado',
                    'xml_validado',
                    'xml_validacion_error',
                    'actualizado_en',
                ]
            )

            secuencia_cfg = (
                Secuencia.objects.filter(
                    empresa=empresa,
                    tipo_documento=self.SECUENCIA_TIPO_DOCUMENTO,
                    activo=True,
                    establecimiento=int(retencion.establecimiento_retencion),
                    punto_emision=int(retencion.punto_emision_retencion),
                )
                .order_by('id')
                .first()
            )
            if secuencia_cfg:
                try:
                    secuencia_actual = int(secuencia_cfg.secuencial or 0)
                    secuencia_guardada = int(retencion.secuencia_retencion)
                except (TypeError, ValueError):
                    secuencia_actual = 0
                    secuencia_guardada = 0
                if secuencia_guardada > secuencia_actual:
                    secuencia_cfg.secuencial = secuencia_guardada
                    secuencia_cfg.save(update_fields=['secuencial'])

        if retencion.xml_validado:
            messages.success(request, f'Retención {retencion.numero_completo} guardada. XML ATS 2.0.0 válido.')
        else:
            messages.warning(request, f'Retención {retencion.numero_completo} guardada, pero el XML tiene observaciones de validación XSD.')
        return redirect('inventario:retenciones_listar')


class DescargarXMLRetencion(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'

    def get(self, request, pk, *args, **kwargs):
        empresa = get_empresa_activa(request)
        retencion = ComprobanteRetencion.objects.filter(empresa=empresa, pk=pk).first()
        if not retencion:
            messages.error(request, 'Retención no encontrada.')
            return redirect('inventario:retenciones_listar')

        if not retencion.xml_generado:
            xml_gen = RetencionXMLGenerator(retencion)
            retencion.clave_acceso = xml_gen.generar_clave_acceso()
            retencion.xml_generado = xml_gen.generar_xml()
            validacion = xml_gen.validar_xml(retencion.xml_generado)
            retencion.xml_validado = validacion.valido
            retencion.xml_validacion_error = '' if validacion.valido else (validacion.errores or validacion.mensaje)
            retencion.save(update_fields=['clave_acceso', 'xml_generado', 'xml_validado', 'xml_validacion_error', 'actualizado_en'])

        nombre = f"retencion_{retencion.numero_completo.replace('-', '_')}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xml"
        response = HttpResponse(retencion.xml_generado, content_type='application/xml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{nombre}"'
        return response
