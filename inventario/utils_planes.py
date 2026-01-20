"""
Decorador y utilidades para verificar límites de planes
"""
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.http import JsonResponse
from django.conf import settings
from django.core.mail import send_mail
from .models_planes import EmpresaPlan
import logging

logger = logging.getLogger(__name__)


def _get_email_destino_empresa(empresa):
    """Obtiene el correo destino principal de la empresa (si existe)."""
    try:
        if getattr(empresa, 'opciones', None) is not None and empresa.opciones.exists():
            correo = empresa.opciones.first().correo
            if correo and correo != 'pendiente@empresa.com':
                return correo
    except Exception:
        pass

    correo = getattr(empresa, 'correo', None)
    if correo and correo != 'pendiente@empresa.com':
        return correo

    return None


def _enviar_email_notificacion_plan(empresa_plan: EmpresaPlan, estado: dict, tipo: str) -> bool:
    """Envía un correo (best-effort) cuando se alcanza 80% o 100% del plan."""
    empresa = empresa_plan.empresa
    to_email = _get_email_destino_empresa(empresa)
    if not to_email:
        logger.warning(f"No se pudo notificar plan para {getattr(empresa, 'ruc', 'N/A')}: sin correo configurado")
        return False

    porcentaje = estado.get('porcentaje_usado', 0)
    usados = estado.get('documentos_usados', empresa_plan.documentos_autorizados)
    limite = estado.get('limite_documentos', empresa_plan.plan.limite_documentos)
    restantes = estado.get('documentos_restantes', max(0, limite - usados))
    dias = getattr(empresa_plan, 'dias_restantes', None)

    if tipo == 'LIMITE':
        subject = f"🚫 Límite de documentos alcanzado ({empresa_plan.plan.nombre})"
        headline = "Ha alcanzado el 100% del límite de su plan."
    else:
        subject = f"⚠️ Aviso: consumo de plan al {porcentaje:.1f}% ({empresa_plan.plan.nombre})"
        headline = "Está cerca de alcanzar el límite de su plan."

    site_url = getattr(settings, 'SITE_URL', '')
    body = (
        f"Hola {getattr(empresa, 'razon_social', 'empresa')},\n\n"
        f"{headline}\n\n"
        f"Plan: {empresa_plan.plan.nombre} ({empresa_plan.plan.codigo})\n"
        f"Uso: {usados}/{limite} documentos autorizados ({porcentaje:.1f}%)\n"
        f"Restantes: {restantes}\n"
        + (f"Días restantes del periodo: {dias}\n" if dias is not None else "")
        + (f"\nPuedes revisar tu cuenta aquí: {site_url}\n" if site_url else "")
        + "\nEste aviso se envía automáticamente.\n"
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
            recipient_list=[to_email],
            fail_silently=True,
        )
        logger.info(f"Notificación de plan enviada a {to_email} para empresa {getattr(empresa, 'ruc', 'N/A')}")
        return True
    except Exception as exc:
        logger.warning(f"Error enviando notificación de plan para {getattr(empresa, 'ruc', 'N/A')}: {exc}")
        return False


def _notificar_si_corresponde(empresa_plan: EmpresaPlan, estado: dict) -> None:
    """Marca flags y envía correo una sola vez por umbral en el periodo actual."""
    if estado.get('alcanzado_limite') and not getattr(empresa_plan, 'notificacion_limite_enviada', False):
        _enviar_email_notificacion_plan(empresa_plan, estado, tipo='LIMITE')
        empresa_plan.notificacion_limite_enviada = True
        empresa_plan.save(update_fields=['notificacion_limite_enviada'])

    elif estado.get('alcanzado_80') and not empresa_plan.notificacion_enviada:
        _enviar_email_notificacion_plan(empresa_plan, estado, tipo='AVISO_80')
        empresa_plan.notificacion_enviada = True
        empresa_plan.save(update_fields=['notificacion_enviada'])


def verificar_limite_plan(view_func):
    """
    Decorador para verificar que la empresa no haya excedido su límite de documentos
    antes de autorizar un nuevo documento.
    
    Uso:
        @verificar_limite_plan
        def autorizar_factura(request, pk):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Obtener empresa activa
        empresa = getattr(request, 'empresa_activa', None)
        if not empresa:
            # Intentar obtener de la sesión
            from .views import get_empresa_activa
            empresa = get_empresa_activa(request)
        
        if not empresa:
            messages.error(request, 'No se pudo determinar la empresa activa.')
            return redirect('inventario:seleccionar_empresa')
        
        # Verificar si la empresa tiene plan
        try:
            empresa_plan = EmpresaPlan.objects.get(empresa=empresa, activo=True)
        except EmpresaPlan.DoesNotExist:
            # Si no tiene plan, permitir (modo legacy/administrador)
            logger.warning(f"Empresa {empresa.ruc} no tiene plan configurado")
            return view_func(request, *args, **kwargs)
        
        # Verificar si el periodo está vencido
        if empresa_plan.periodo_vencido:
            messages.error(
                request,
                f'⚠️ El periodo de su plan ha vencido. Por favor contacte con soporte para renovar.'
            )
            return redirect(request.META.get('HTTP_REFERER', 'inventario:dashboard'))
        
        # Verificar límite de documentos
        estado = empresa_plan.verificar_limite()

        # Notificar (email) si corresponde
        _notificar_si_corresponde(empresa_plan, estado)
        
        if estado['alcanzado_limite']:
            # Límite alcanzado - bloquear autorización
            messages.error(
                request,
                f'🚫 Ha alcanzado el límite de {estado["limite_documentos"]} documentos de su plan {empresa_plan.plan.nombre}. '
                f'Por favor actualice su plan para continuar autorizando documentos.'
            )
            return redirect(request.META.get('HTTP_REFERER', 'inventario:dashboard'))
        
        elif estado['alcanzado_80'] and not empresa_plan.notificacion_enviada:
            # Advertencia al 80% - mostrar pero permitir
            messages.warning(
                request,
                f'⚠️ Atención: Ha utilizado {estado["porcentaje_usado"]:.1f}% de su plan. '
                f'Le quedan {estado["documentos_restantes"]} documentos de {estado["limite_documentos"]}.'
            )
            # Marcar que ya se notificó
            empresa_plan.notificacion_enviada = True
            empresa_plan.save(update_fields=['notificacion_enviada'])
        
        # Permitir la autorización
        return view_func(request, *args, **kwargs)
    
    return wrapper


def incrementar_contador_documentos(empresa):
    """
    Incrementa el contador de documentos autorizados para una empresa.
    Debe llamarse después de que un documento sea autorizado exitosamente.
    
    Args:
        empresa: Instancia de Empresa
    """
    try:
        empresa_plan = EmpresaPlan.objects.get(empresa=empresa, activo=True)
        empresa_plan.incrementar_contador()
        logger.info(f"Contador incrementado para {empresa.ruc}: {empresa_plan.documentos_autorizados}/{empresa_plan.plan.limite_documentos}")
    except EmpresaPlan.DoesNotExist:
        logger.warning(f"Empresa {empresa.ruc} no tiene plan configurado - contador no incrementado")


def obtener_estado_plan(empresa):
    """
    Obtiene el estado actual del plan de una empresa.
    
    Args:
        empresa: Instancia de Empresa
        
    Returns:
        dict con información del plan o None si no tiene plan
    """
    try:
        empresa_plan = EmpresaPlan.objects.select_related('plan').get(empresa=empresa, activo=True)
        estado = empresa_plan.verificar_limite()
        
        return {
            'tiene_plan': True,
            'plan_nombre': empresa_plan.plan.nombre,
            'plan_codigo': empresa_plan.plan.codigo,
            'documentos_usados': estado['documentos_usados'],
            'limite_documentos': estado['limite_documentos'],
            'porcentaje_usado': estado['porcentaje_usado'],
            'documentos_restantes': estado['documentos_restantes'],
            'puede_autorizar': estado['puede_autorizar'],
            'alcanzado_80': estado['alcanzado_80'],
            'alcanzado_limite': estado['alcanzado_limite'],
            'dias_restantes': empresa_plan.dias_restantes,
            'periodo_vencido': empresa_plan.periodo_vencido,
            'fecha_fin': empresa_plan.fecha_fin,
        }
    except EmpresaPlan.DoesNotExist:
        return {
            'tiene_plan': False,
            'puede_autorizar': True,  # Permitir si no tiene plan (legacy)
        }


def obtener_estado_plan_y_notificar(empresa):
    """Igual que obtener_estado_plan, pero también dispara email/flags si corresponde."""
    try:
        empresa_plan = EmpresaPlan.objects.select_related('plan').get(empresa=empresa, activo=True)
        estado = empresa_plan.verificar_limite()
        _notificar_si_corresponde(empresa_plan, estado)
    except EmpresaPlan.DoesNotExist:
        return {
            'tiene_plan': False,
            'puede_autorizar': True,
        }

    return {
        'tiene_plan': True,
        'plan_nombre': empresa_plan.plan.nombre,
        'plan_codigo': empresa_plan.plan.codigo,
        'documentos_usados': estado['documentos_usados'],
        'limite_documentos': estado['limite_documentos'],
        'porcentaje_usado': estado['porcentaje_usado'],
        'documentos_restantes': estado['documentos_restantes'],
        'puede_autorizar': estado['puede_autorizar'],
        'alcanzado_80': estado['alcanzado_80'],
        'alcanzado_limite': estado['alcanzado_limite'],
        'dias_restantes': empresa_plan.dias_restantes,
        'periodo_vencido': empresa_plan.periodo_vencido,
        'fecha_fin': empresa_plan.fecha_fin,
    }


def api_verificar_limite(request):
    """
    Vista API para verificar el límite del plan via AJAX.
    Útil para mostrar modales antes de autorizar.
    
    Returns:
        JsonResponse con el estado del plan
    """
    from .views import get_empresa_activa
    
    empresa = get_empresa_activa(request)
    if not empresa:
        return JsonResponse({'error': 'No hay empresa activa'}, status=400)
    
    estado_plan = obtener_estado_plan(empresa)
    return JsonResponse(estado_plan)
