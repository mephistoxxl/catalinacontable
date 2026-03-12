from __future__ import annotations

import logging

from django.utils import timezone


logger = logging.getLogger(__name__)


def liquidacion_esta_autorizada(liquidacion) -> bool:
    estado = (getattr(liquidacion, 'estado_sri', '') or getattr(liquidacion, 'estado', '') or '').strip().upper()
    return estado in {'AUTORIZADA', 'AUTORIZADO'} or bool(
        getattr(liquidacion, 'numero_autorizacion', None) and getattr(liquidacion, 'fecha_autorizacion', None)
    )


def enviar_email_automatico_liquidacion(liquidacion) -> bool:
    if not liquidacion_esta_autorizada(liquidacion):
        return False

    if getattr(liquidacion, 'email_enviado', False):
        return False

    if (
        liquidacion_esta_autorizada(liquidacion)
        and (
            not getattr(liquidacion, 'numero_autorizacion', None)
            or not getattr(liquidacion, 'fecha_autorizacion', None)
            or not getattr(liquidacion, 'xml_autorizado', None)
        )
        and getattr(liquidacion, 'clave_acceso', None)
    ):
        try:
            from inventario.liquidacion_compra.integracion_sri_liquidacion import IntegracionSRILiquidacion

            IntegracionSRILiquidacion(liquidacion.empresa).consultar_estado_actual(liquidacion)
            liquidacion.refresh_from_db(fields=[
                'estado',
                'estado_sri',
                'numero_autorizacion',
                'fecha_autorizacion',
                'xml_autorizado',
            ])
        except Exception:
            logger.exception('[LIQ EMAIL] No se pudo refrescar autorización para liquidación %s', liquidacion.id)

    if not liquidacion_esta_autorizada(liquidacion):
        return False

    from inventario.documentos_email.services import DocumentEmailService

    servicio = DocumentEmailService(liquidacion.empresa)
    liquidacion.email_envio_intentos = (getattr(liquidacion, 'email_envio_intentos', 0) or 0) + 1

    try:
        resultado = servicio.send_liquidacion(liquidacion)
        if not resultado.success:
            liquidacion.email_ultimo_error = resultado.message
            liquidacion.save(update_fields=['email_envio_intentos', 'email_ultimo_error'])
            logger.warning('[LIQ EMAIL] No se envió liquidación %s: %s', liquidacion.id, resultado.message)
            return False

        liquidacion.email_enviado = True
        liquidacion.email_enviado_at = timezone.now()
        liquidacion.email_ultimo_error = None
        liquidacion.save(update_fields=['email_enviado', 'email_enviado_at', 'email_envio_intentos', 'email_ultimo_error'])
        logger.info('[LIQ EMAIL] Liquidación %s enviada a %s', liquidacion.id, ', '.join(resultado.recipients))
        return True
    except Exception as exc:
        liquidacion.email_ultimo_error = str(exc)
        liquidacion.save(update_fields=['email_envio_intentos', 'email_ultimo_error'])
        logger.exception('[LIQ EMAIL] Error enviando liquidación %s', liquidacion.id)
        return False