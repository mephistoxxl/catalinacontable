from __future__ import annotations

import logging

from django.utils import timezone


logger = logging.getLogger(__name__)


def enviar_email_automatico_liquidacion(liquidacion) -> bool:
    if not liquidacion.numero_autorizacion or not liquidacion.fecha_autorizacion:
        return False

    if getattr(liquidacion, 'email_enviado', False):
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