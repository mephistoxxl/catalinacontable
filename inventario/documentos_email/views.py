from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from inventario.models import GuiaRemision
from inventario.liquidacion_compra.models import LiquidacionCompra
from inventario.nota_credito.models import NotaCredito
from inventario.nota_debito.models import NotaDebito
from inventario.retenciones.models import ComprobanteRetencion

from .services import DocumentEmailService


def _empresa_activa(request):
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id:
        return None
    return request.user.empresas.filter(id=empresa_id).first()


def _json_from_result(resultado):
    payload = {
        'success': bool(resultado.success),
        'message': resultado.message,
        'recipients': resultado.recipients,
    }
    return JsonResponse(payload, status=200 if resultado.success else 400)


@login_required
@require_http_methods(["GET", "POST"])
def enviar_email_retencion(request, pk):
    empresa = _empresa_activa(request)
    if not empresa:
        return JsonResponse({'success': False, 'message': 'Empresa no válida.'}, status=403)

    retencion = get_object_or_404(ComprobanteRetencion, pk=pk, empresa=empresa)
    servicio = DocumentEmailService(empresa)
    resultado = servicio.send_retencion(retencion)
    return _json_from_result(resultado)


@login_required
@require_http_methods(["GET", "POST"])
def enviar_email_nota_credito(request, pk):
    empresa = _empresa_activa(request)
    if not empresa:
        return JsonResponse({'success': False, 'message': 'Empresa no válida.'}, status=403)

    nota_credito = get_object_or_404(NotaCredito, pk=pk, empresa=empresa)
    servicio = DocumentEmailService(empresa)
    resultado = servicio.send_nota_credito(nota_credito)
    return _json_from_result(resultado)


@login_required
@require_http_methods(["GET", "POST"])
def enviar_email_nota_debito(request, pk):
    empresa = _empresa_activa(request)
    if not empresa:
        return JsonResponse({'success': False, 'message': 'Empresa no válida.'}, status=403)

    nota_debito = get_object_or_404(NotaDebito, pk=pk, empresa=empresa)
    servicio = DocumentEmailService(empresa)
    resultado = servicio.send_nota_debito(nota_debito)
    return _json_from_result(resultado)


@login_required
@require_http_methods(["GET", "POST"])
def enviar_email_guia(request, guia_id):
    empresa = _empresa_activa(request)
    if not empresa:
        return JsonResponse({'success': False, 'message': 'Empresa no válida.'}, status=403)

    guia = get_object_or_404(GuiaRemision, id=guia_id, empresa=empresa)
    servicio = DocumentEmailService(empresa)
    resultado = servicio.send_guia(guia)
    return _json_from_result(resultado)


@login_required
@require_http_methods(["GET", "POST"])
def enviar_email_liquidacion(request, pk):
    empresa = _empresa_activa(request)
    if not empresa:
        return JsonResponse({'success': False, 'message': 'Empresa no válida.'}, status=403)

    liquidacion = get_object_or_404(LiquidacionCompra, pk=pk, empresa=empresa)
    servicio = DocumentEmailService(empresa)
    resultado = servicio.send_liquidacion(liquidacion)
    return _json_from_result(resultado)
