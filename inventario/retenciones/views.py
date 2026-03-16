from __future__ import annotations

import json
import logging
import os
import tempfile
from decimal import Decimal
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from ..mixins import RequireEmpresaActivaMixin, get_empresa_activa
from ..models import Opciones, Secuencia
from .forms import ComprobanteRetencionForm
from .models import ComprobanteRetencion, RetencionDetalle
from .services import (
    calcular_valor_retenido,
    porcentaje_iva_por_codigo,
    porcentaje_renta_sugerido,
)
from .xml_generator_retencion import RetencionXMLGenerator
from ..sri.ambiente import obtener_ambiente_sri
from ..sri.firmador_xades_sri import XAdESError, firmar_xml_xades_bes
from ..sri.sri_client import SRIClient

logger = logging.getLogger(__name__)


PORCENTAJES_IVA_RETENCION_PERMITIDOS = {
    Decimal('10.00'),
    Decimal('20.00'),
    Decimal('30.00'),
    Decimal('50.00'),
    Decimal('70.00'),
}

CODIGOS_RENTA_VIGENTES = {
    '303', '303A', '304', '304A', '304B', '304C', '304D', '304E',
    '307', '308', '309', '310', '311', '312', '312A', '312C',
    '314A', '314B', '314C', '319', '320', '322', '323', '323A',
    '323B', '323E', '323M', '323P', '324A', '324B', '332', '332A',
    '332B', '332C', '332D', '332E', '332F', '332G', '332I', '334',
    '335', '338', '340', '343', '343A', '343B', '343C', '344', '3440',
    '344A', '346', '3482', '350',
}

CODIGOS_IVA_VIGENTES = {'721', '723', '725', '727', '7'}


def _to_decimal(value, default: str = '0.00') -> Decimal:
    try:
        return Decimal(str(value or default))
    except Exception:
        return Decimal(default)


def _cargar_detalles_json(request) -> tuple[list[dict], list[dict]]:
    def _cargar(raw: str) -> list[dict]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
        except Exception:
            return []
        return []

    renta = _cargar((request.POST.get('renta_detalles_json') or '').strip())
    iva = _cargar((request.POST.get('iva_detalles_json') or '').strip())
    return renta, iva


def _normalizar_detalles_payload(renta_rows: list[dict], iva_rows: list[dict], form: ComprobanteRetencionForm) -> list[dict]:
    detalles: list[dict] = []

    for row in renta_rows:
        codigo = (row.get('codigo') or '304B').strip()
        if codigo not in CODIGOS_RENTA_VIGENTES:
            raise ValidationError(f'Código de retención renta no vigente o no permitido: {codigo}.')
        base = _to_decimal(row.get('base'))
        porcentaje = _to_decimal(row.get('porcentaje'))
        if porcentaje <= 0:
            porcentaje = porcentaje_renta_sugerido(codigo)
        if base > 0 and porcentaje > 0:
            detalles.append(
                {
                    'tipo_impuesto': 'RENTA',
                    'codigo_retencion': codigo,
                    'descripcion_retencion': (row.get('descripcion') or 'Retención Renta').strip(),
                    'base_imponible': base,
                    'porcentaje_retener': porcentaje,
                    'valor_retenido': calcular_valor_retenido(base, porcentaje),
                }
            )

    for row in iva_rows:
        codigo = (row.get('codigo') or '721').strip()
        if codigo not in CODIGOS_IVA_VIGENTES:
            raise ValidationError(f'Código de retención IVA no vigente o no permitido: {codigo}.')
        base = _to_decimal(row.get('base'))
        porcentaje = _to_decimal(row.get('porcentaje'))
        if porcentaje <= 0:
            porcentaje = porcentaje_iva_por_codigo(codigo)
        porcentaje_2 = Decimal(str(porcentaje)).quantize(Decimal('0.00'))
        if porcentaje_2 not in PORCENTAJES_IVA_RETENCION_PERMITIDOS:
            raise ValidationError(
                'El porcentaje de retención de IVA debe ser uno de: 10%, 20%, 30%, 50% o 70%.'
            )
        if base > 0 and porcentaje > 0:
            detalles.append(
                {
                    'tipo_impuesto': 'IVA',
                    'codigo_retencion': codigo,
                    'descripcion_retencion': (row.get('descripcion') or 'Retención IVA').strip(),
                    'base_imponible': base,
                    'porcentaje_retener': porcentaje,
                    'valor_retenido': calcular_valor_retenido(base, porcentaje),
                }
            )

    if detalles:
        return detalles

    renta_base = form.cleaned_data.get('renta_base') or Decimal('0.00')
    renta_codigo = (form.cleaned_data.get('codigo_renta') or '304B').strip()
    renta_porcentaje = form.cleaned_data.get('renta_porcentaje') or Decimal('0.00')
    if renta_porcentaje <= 0:
        renta_porcentaje = porcentaje_renta_sugerido(renta_codigo)
    if renta_base > 0 and renta_porcentaje > 0:
        detalles.append(
            {
                'tipo_impuesto': 'RENTA',
                'codigo_retencion': renta_codigo,
                'descripcion_retencion': 'Retención Renta',
                'base_imponible': renta_base,
                'porcentaje_retener': renta_porcentaje,
                'valor_retenido': calcular_valor_retenido(renta_base, renta_porcentaje),
            }
        )

    iva_base = form.cleaned_data.get('iva_base') or Decimal('0.00')
    iva_codigo = (form.cleaned_data.get('codigo_iva') or '721').strip()
    if iva_codigo not in CODIGOS_IVA_VIGENTES:
        raise ValidationError(f'Código de retención IVA no vigente o no permitido: {iva_codigo}.')
    iva_porcentaje = porcentaje_iva_por_codigo(iva_codigo)
    iva_porcentaje_2 = Decimal(str(iva_porcentaje)).quantize(Decimal('0.00'))
    if iva_porcentaje_2 not in PORCENTAJES_IVA_RETENCION_PERMITIDOS:
        raise ValidationError(
            'El porcentaje de retención de IVA debe ser uno de: 10%, 20%, 30%, 50% o 70%.'
        )
    if iva_base > 0 and iva_porcentaje > 0:
        detalles.append(
            {
                'tipo_impuesto': 'IVA',
                'codigo_retencion': iva_codigo,
                'descripcion_retencion': 'Retención IVA',
                'base_imponible': iva_base,
                'porcentaje_retener': iva_porcentaje,
                'valor_retenido': calcular_valor_retenido(iva_base, iva_porcentaje),
            }
        )

    total_iva_retenido = sum(
        (d['valor_retenido'] for d in detalles if d.get('tipo_impuesto') == 'IVA'),
        Decimal('0.00')
    )
    monto_iva_doc = (form.cleaned_data.get('monto_iva') or Decimal('0.00')).quantize(Decimal('0.01'))
    if total_iva_retenido > monto_iva_doc:
        raise ValidationError(
            'El valor de IVA retenido no puede ser mayor al IVA del documento de sustento.'
        )

    return detalles


def _serializar_detalles(retencion: ComprobanteRetencion) -> tuple[str, str]:
    renta = []
    iva = []
    for d in retencion.detalles.all().order_by('id'):
        row = {
            'codigo': d.codigo_retencion,
            'descripcion': d.descripcion_retencion,
            'base': f'{d.base_imponible:.2f}',
            'porcentaje': f'{d.porcentaje_retener:.4f}',
        }
        if d.tipo_impuesto == 'RENTA':
            renta.append(row)
        elif d.tipo_impuesto == 'IVA':
            iva.append(row)
    return json.dumps(renta), json.dumps(iva)


def _encolar_reintentos_retencion(retencion: ComprobanteRetencion) -> bool:
    try:
        from inventario.sri.rq_jobs import enqueue_poll_autorizacion_retencion

        return enqueue_poll_autorizacion_retencion(
            retencion_id=retencion.id,
            empresa_id=retencion.empresa_id,
            delay_seconds=30,
            attempt=1,
            max_attempts=240,
        )
    except Exception as exc:
        logger.warning('No se pudo encolar reintento SRI para retención %s: %s', retencion.id, exc)
        return False


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

        try:
            pendientes = (
                ComprobanteRetencion.objects.filter(empresa=empresa, estado_sri__in=['PENDIENTE', 'RECIBIDA'])
                .exclude(clave_acceso='')
                .order_by('-actualizado_en')[:10]
            )
            for ret in pendientes:
                _encolar_reintentos_retencion(ret)
        except Exception as exc:
            logger.warning('No se pudo iniciar auto-reintentos SRI de retenciones: %s', exc)

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

        renta_rows, iva_rows = _cargar_detalles_json(request)
        try:
            detalles = _normalizar_detalles_payload(renta_rows, iva_rows, form)
        except ValidationError as exc:
            form.add_error(None, str(exc))
            messages.error(request, 'Por favor corrige los campos del formulario de retención.')
            return render(
                request,
                self.template_name,
                {
                    'form': form,
                    'titulo': 'Emitir Retención',
                    'menu_actual': 'compras',
                    'opcion_actual': 'emitir_retencion',
                    'renta_detalles_iniciales': json.dumps(renta_rows),
                    'iva_detalles_iniciales': json.dumps(iva_rows),
                },
            )

        with transaction.atomic():
            retencion = form.save(commit=False)
            retencion.empresa = empresa
            retencion.usuario_creacion = request.user
            retencion.limpiar_estado_xml()
            retencion.save()

            for det in detalles:
                RetencionDetalle.objects.create(comprobante=retencion, **det)

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

        nivel, mensaje = _procesar_envio_retencion_sri(retencion, empresa)
        _agregar_mensaje_request(request, nivel, mensaje)
        return redirect('inventario:retenciones_listar')


class EditarRetencion(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'
    template_name = 'inventario/retencion/crear.html'

    def _contexto(self, form, retencion: ComprobanteRetencion):
        renta_json, iva_json = _serializar_detalles(retencion)
        return {
            'form': form,
            'titulo': 'Editar Retención',
            'menu_actual': 'compras',
            'opcion_actual': 'listar_retenciones',
            'modo_edicion': True,
            'retencion': retencion,
            'renta_detalles_iniciales': renta_json,
            'iva_detalles_iniciales': iva_json,
        }

    def get(self, request, pk, *args, **kwargs):
        empresa = get_empresa_activa(request)
        retencion = ComprobanteRetencion.objects.filter(empresa=empresa, pk=pk).first()
        if not retencion:
            messages.error(request, 'Retención no encontrada.')
            return redirect('inventario:retenciones_listar')

        renta = retencion.detalles.filter(tipo_impuesto='RENTA').order_by('id').first()
        iva = retencion.detalles.filter(tipo_impuesto='IVA').order_by('id').first()
        initial = {}
        if renta:
            initial.update({'renta_base': renta.base_imponible, 'renta_porcentaje': renta.porcentaje_retener, 'codigo_renta': renta.codigo_retencion})
        if iva:
            initial.update({'iva_base': iva.base_imponible, 'iva_porcentaje': iva.porcentaje_retener, 'codigo_iva': iva.codigo_retencion})

        form = ComprobanteRetencionForm(instance=retencion, initial=initial)
        return render(request, self.template_name, self._contexto(form, retencion))

    def post(self, request, pk, *args, **kwargs):
        empresa = get_empresa_activa(request)
        retencion = ComprobanteRetencion.objects.filter(empresa=empresa, pk=pk).first()
        if not retencion:
            messages.error(request, 'Retención no encontrada.')
            return redirect('inventario:retenciones_listar')

        if retencion.estado_sri == 'AUTORIZADA':
            messages.error(request, 'No se puede editar una retención ya autorizada por SRI.')
            return redirect('inventario:retenciones_listar')

        form = ComprobanteRetencionForm(request.POST, instance=retencion)
        if not form.is_valid():
            messages.error(request, 'Por favor corrige los campos del formulario de retención.')
            return render(request, self.template_name, self._contexto(form, retencion))

        renta_rows, iva_rows = _cargar_detalles_json(request)
        try:
            detalles = _normalizar_detalles_payload(renta_rows, iva_rows, form)
        except ValidationError as exc:
            form.add_error(None, str(exc))
            messages.error(request, 'Por favor corrige los campos del formulario de retención.')
            return render(
                request,
                self.template_name,
                {
                    **self._contexto(form, retencion),
                    'renta_detalles_iniciales': json.dumps(renta_rows),
                    'iva_detalles_iniciales': json.dumps(iva_rows),
                },
            )

        with transaction.atomic():
            retencion = form.save(commit=False)
            retencion.empresa = empresa
            retencion.estado_sri = ''
            retencion.numero_autorizacion = ''
            retencion.autorizacion_retencion = ''
            retencion.clave_acceso = ''
            retencion.limpiar_estado_xml()
            retencion.save()

            retencion.detalles.all().delete()
            for det in detalles:
                RetencionDetalle.objects.create(comprobante=retencion, **det)

            retencion.recalcular_totales()
            xml_gen = RetencionXMLGenerator(retencion)
            retencion.clave_acceso = xml_gen.generar_clave_acceso()
            retencion.xml_generado = xml_gen.generar_xml()
            validacion = xml_gen.validar_xml(retencion.xml_generado)
            retencion.xml_validado = validacion.valido
            retencion.xml_validacion_error = '' if validacion.valido else (validacion.errores or validacion.mensaje)
            retencion.save(update_fields=['total_retencion_renta', 'total_retencion_iva', 'total_retenido', 'clave_acceso', 'xml_generado', 'xml_firmado', 'xml_firmado_en', 'xml_validado', 'xml_validacion_error', 'estado_sri', 'numero_autorizacion', 'autorizacion_retencion', 'actualizado_en'])

        nivel, mensaje = _procesar_envio_retencion_sri(retencion, empresa)
        _agregar_mensaje_request(request, nivel, mensaje)
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


class DescargarXMLFirmadoRetencion(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'

    def get(self, request, pk, *args, **kwargs):
        empresa = get_empresa_activa(request)
        retencion = ComprobanteRetencion.objects.filter(empresa=empresa, pk=pk).first()
        if not retencion:
            messages.error(request, 'Retención no encontrada.')
            return redirect('inventario:retenciones_listar')

        if not retencion.xml_firmado:
            messages.warning(request, 'La retención aún no tiene XML firmado guardado.')
            return redirect('inventario:retenciones_listar')

        nombre = f"retencion_firmada_{retencion.numero_completo.replace('-', '_')}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xml"
        response = HttpResponse(retencion.xml_firmado, content_type='application/xml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{nombre}"'
        return response


class DescargarPDFRetencion(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'

    def get(self, request, pk, *args, **kwargs):
        empresa = get_empresa_activa(request)
        retencion = ComprobanteRetencion.objects.filter(empresa=empresa, pk=pk).first()
        if not retencion:
            messages.error(request, 'Retencion no encontrada.')
            return redirect('inventario:retenciones_listar')

        try:
            from .ride_generator_retencion import RIDERetencionGenerator

            opciones = Opciones.objects.for_tenant(retencion.empresa).first()
            generator = RIDERetencionGenerator(retencion, opciones)
            pdf_buffer = generator.generar_pdf()

            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            filename = f"RET_{retencion.numero_completo.replace('-', '_')}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as exc:
            logger.exception('Error generando PDF de retencion %s: %s', retencion.id, exc)
            messages.error(request, f'Error al generar PDF: {str(exc)}')
            return redirect('inventario:retenciones_listar')


def _normalizar_estado_sri(valor: str) -> str:
    estado = (valor or '').strip().upper()
    equivalencias = {
        'AUTORIZADO': 'AUTORIZADA',
        'AUTORIZADA': 'AUTORIZADA',
        'RECIBIDA': 'RECIBIDA',
        'PENDIENTE': 'PENDIENTE',
        'NO AUTORIZADO': 'RECHAZADA',
        'NO_AUTORIZADO': 'RECHAZADA',
        'NO AUTORIZADA': 'RECHAZADA',
        'NO_AUTORIZADA': 'RECHAZADA',
        'RECHAZADA': 'RECHAZADA',
        'DEVUELTA': 'RECHAZADA',
        'ERROR': 'ERROR',
    }
    return equivalencias.get(estado, estado)


def _extraer_autorizacion(resultado: dict) -> tuple[str, str]:
    numero = ''
    fecha = ''
    autorizaciones = resultado.get('autorizaciones') or []
    if autorizaciones and isinstance(autorizaciones, list):
        aut0 = autorizaciones[0] or {}
        if isinstance(aut0, dict):
            numero_raw = aut0.get('numeroAutorizacion') or aut0.get('numero_autorizacion') or ''
            fecha_raw = aut0.get('fechaAutorizacion') or aut0.get('fecha_autorizacion') or ''

            numero = str(numero_raw).strip() if numero_raw is not None else ''
            if isinstance(fecha_raw, datetime):
                fecha = fecha_raw.strftime('%Y-%m-%d %H:%M:%S')
            else:
                fecha = str(fecha_raw).strip() if fecha_raw is not None else ''
    return numero, fecha


def _formatear_fecha_autorizacion(fecha_txt: str) -> str:
    if not fecha_txt:
        return ''
    candidatos = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
    ]
    limpio = fecha_txt.split('.')[0].replace('Z', '')
    for fmt in candidatos:
        try:
            return datetime.strptime(limpio, fmt).strftime('%d/%m/%Y %H:%M:%S')
        except ValueError:
            continue
    return fecha_txt


def _agregar_mensaje_request(request, nivel: str, texto: str) -> None:
    if nivel == 'success':
        messages.success(request, texto)
    elif nivel == 'warning':
        messages.warning(request, texto)
    elif nivel == 'info':
        messages.info(request, texto)
    else:
        messages.error(request, texto)


def _formatear_mensajes_sri_detallado(mensajes: list) -> str:
    """Convierte los mensajes del SRI en texto legible con código y detalle adicional."""
    partes = []
    for msg in (mensajes or []):
        if isinstance(msg, dict):
            identificador = str(msg.get('identificador') or '').strip()
            texto = str(msg.get('mensaje') or '').strip()
            adicional = str(
                msg.get('informacionAdicional')
                or msg.get('informacion_adicional')
                or ''
            ).strip()

            segmento = ''
            if identificador:
                segmento += f'[{identificador}] '
            segmento += texto or 'Mensaje sin descripción.'
            if adicional:
                segmento += f' - {adicional}'
            partes.append(segmento)
        else:
            texto = str(msg).strip()
            if texto:
                partes.append(texto)

    return ' | '.join(partes)


def _procesar_envio_retencion_sri(retencion: ComprobanteRetencion, empresa) -> tuple[str, str]:
    if retencion.estado_sri == 'AUTORIZADA' and (retencion.numero_autorizacion or '').strip():
        return 'info', f'Retención {retencion.numero_completo} ya está autorizada en SRI.'

    fd_xml = None
    fd_firmado = None
    path_xml = None
    path_firmado = None
    try:
        xml_gen = RetencionXMLGenerator(retencion)
        if not retencion.clave_acceso:
            retencion.clave_acceso = xml_gen.generar_clave_acceso()
        if not retencion.xml_generado:
            retencion.xml_generado = xml_gen.generar_xml()

        validacion = xml_gen.validar_xml(retencion.xml_generado)
        retencion.xml_validado = validacion.valido
        retencion.xml_validacion_error = '' if validacion.valido else (validacion.errores or validacion.mensaje)
        if not retencion.xml_validado:
            retencion.estado_sri = 'ERROR'
            retencion.save(update_fields=['clave_acceso', 'xml_generado', 'xml_validado', 'xml_validacion_error', 'estado_sri', 'actualizado_en'])
            return 'error', 'El XML de retención no es válido según XSD. Corrige antes de enviar al SRI.'

        ambiente = obtener_ambiente_sri(empresa)
        cliente = SRIClient(ambiente='produccion' if ambiente == '2' else 'pruebas')

        fd_xml, path_xml = tempfile.mkstemp(prefix='retencion_', suffix='.xml')
        fd_firmado, path_firmado = tempfile.mkstemp(prefix='retencion_', suffix='_firmado.xml')
        os.close(fd_xml)
        os.close(fd_firmado)

        with open(path_xml, 'w', encoding='utf-8') as src:
            src.write(retencion.xml_generado)

        firmar_xml_xades_bes(path_xml, path_firmado, empresa=empresa)

        with open(path_firmado, 'r', encoding='utf-8') as firmado_file:
            retencion.xml_firmado = firmado_file.read()
        retencion.xml_firmado_en = timezone.now()

        resultado_envio = cliente.enviar_comprobante(retencion.xml_firmado, retencion.clave_acceso)
        estado_recepcion = _normalizar_estado_sri(resultado_envio.get('estado'))
        retencion.estado_sri = estado_recepcion or 'ERROR'

        if estado_recepcion in {'RECIBIDA', 'PENDIENTE'}:
            resultado_auth = cliente.consultar_autorizacion(retencion.clave_acceso)
            estado_auth = _normalizar_estado_sri(resultado_auth.get('estado'))
            numero_aut, fecha_aut = _extraer_autorizacion(resultado_auth)
            if numero_aut:
                retencion.numero_autorizacion = numero_aut
                retencion.autorizacion_retencion = numero_aut
            retencion.estado_sri = estado_auth or retencion.estado_sri

            if retencion.estado_sri == 'AUTORIZADA':
                msg_fecha = _formatear_fecha_autorizacion(fecha_aut)
                if msg_fecha:
                    mensaje = f'Retención {retencion.numero_completo} autorizada en SRI ({msg_fecha}).'
                else:
                    mensaje = f'Retención {retencion.numero_completo} autorizada en SRI.'
                nivel = 'success'
            elif retencion.estado_sri in {'PENDIENTE', 'RECIBIDA'}:
                _encolar_reintentos_retencion(retencion)
                mensaje = 'Retención enviada al SRI y pendiente de autorización. El sistema seguirá reintentando automáticamente.'
                nivel = 'warning'
            else:
                mensajes_auth = resultado_auth.get('mensajes') or []
                mensaje_auth = _formatear_mensajes_sri_detallado(mensajes_auth) or 'No autorizada por el SRI.'
                mensaje = f'Retención rechazada por SRI: {mensaje_auth}'
                nivel = 'error'
        else:
            mensajes_envio = resultado_envio.get('mensajes') or []
            mensaje_envio = _formatear_mensajes_sri_detallado(mensajes_envio) or 'No fue recibida por SRI.'
            mensaje = f'Error en recepción SRI: {mensaje_envio}'
            nivel = 'error'

        retencion.save(update_fields=['clave_acceso', 'xml_generado', 'xml_firmado', 'xml_firmado_en', 'xml_validado', 'xml_validacion_error', 'estado_sri', 'numero_autorizacion', 'autorizacion_retencion', 'actualizado_en'])
        return nivel, mensaje
    except XAdESError as err:
        retencion.estado_sri = 'ERROR'
        retencion.save(update_fields=['estado_sri', 'actualizado_en'])
        return 'error', f'Error de firma electrónica: {err}'
    except Exception as exc:
        retencion.estado_sri = 'ERROR'
        retencion.save(update_fields=['estado_sri', 'actualizado_en'])
        return 'error', f'No se pudo procesar la retención en SRI: {exc}'
    finally:
        for p in (path_xml, path_firmado):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass


class AutorizarRetencion(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'

    def post(self, request, pk, *args, **kwargs):
        empresa = get_empresa_activa(request)
        retencion = ComprobanteRetencion.objects.filter(empresa=empresa, pk=pk).first()
        if not retencion:
            messages.error(request, 'Retención no encontrada.')
            return redirect('inventario:retenciones_listar')

        nivel, mensaje = _procesar_envio_retencion_sri(retencion, empresa)
        _agregar_mensaje_request(request, nivel, mensaje)

        return redirect('inventario:retenciones_listar')


class ConsultarEstadoRetencion(LoginRequiredMixin, RequireEmpresaActivaMixin, View):
    login_url = '/inventario/login'

    def post(self, request, pk, *args, **kwargs):
        empresa = get_empresa_activa(request)
        retencion = ComprobanteRetencion.objects.filter(empresa=empresa, pk=pk).first()
        if not retencion:
            messages.error(request, 'Retención no encontrada.')
            return redirect('inventario:retenciones_listar')

        if not retencion.clave_acceso:
            messages.error(request, 'La retención no tiene clave de acceso. Genera el XML primero.')
            return redirect('inventario:retenciones_listar')

        try:
            ambiente = obtener_ambiente_sri(empresa)
            cliente = SRIClient(ambiente='produccion' if ambiente == '2' else 'pruebas')
            resultado = cliente.consultar_autorizacion(retencion.clave_acceso)

            estado = _normalizar_estado_sri(resultado.get('estado'))
            numero_aut, fecha_aut = _extraer_autorizacion(resultado)
            if numero_aut:
                retencion.numero_autorizacion = numero_aut
                retencion.autorizacion_retencion = numero_aut
            if estado:
                retencion.estado_sri = estado
            retencion.save(update_fields=['estado_sri', 'numero_autorizacion', 'autorizacion_retencion', 'actualizado_en'])

            if retencion.estado_sri == 'AUTORIZADA':
                msg_fecha = _formatear_fecha_autorizacion(fecha_aut)
                messages.success(request, f'Retención autorizada. {msg_fecha}'.strip())
            elif retencion.estado_sri in {'PENDIENTE', 'RECIBIDA'}:
                messages.info(request, 'Retención aún pendiente de autorización en SRI.')
            else:
                mensajes = resultado.get('mensajes') or []
                mensaje = _formatear_mensajes_sri_detallado(mensajes) or 'Estado consultado sin autorización.'
                messages.warning(request, f'Estado SRI: {retencion.estado_sri}. {mensaje}')
        except Exception as exc:
            messages.error(request, f'No se pudo consultar estado SRI: {exc}')

        return redirect('inventario:retenciones_listar')
