import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


PENDING_STATES = {"PENDIENTE", "RECIBIDA", "EN_PROCESO", "EN_PROCESAMIENTO", "PROCESANDO", "PROCESAMIENTO"}
FINAL_OK_STATES = {"AUTORIZADA", "AUTORIZADO"}
FINAL_FAIL_STATES = {"RECHAZADA", "NO_AUTORIZADA", "NO AUTORIZADA", "NO_AUTORIZADO", "NO AUTORIZADO", "DEVUELTA", "ERROR"}


def _normalize_state(value: str | None) -> str:
    return str(value or "").upper().strip().replace(" ", "_")


def enqueue_poll_autorizacion_factura(
    *,
    factura_id: int,
    empresa_id: int,
    delay_seconds: int = 30,
    attempt: int = 1,
    max_attempts: int = 240,
) -> bool:
    """Encola (o re-encola) un poll de autorización SRI en la cola `sri`.

    Retorna True si se intentó encolar (aunque ya exista), False si no se pudo.
    """
    try:
        import django_rq
        from rq.exceptions import NoSuchJobError  # noqa: F401

        queue = django_rq.get_queue("sri")
        job_id = f"sri_poll_autorizacion_{empresa_id}_{factura_id}"

        queue.enqueue_in(
            timedelta(seconds=max(0, int(delay_seconds))),
            poll_autorizacion_factura,
            factura_id,
            empresa_id,
            attempt,
            max_attempts,
            job_id=job_id,
            result_ttl=0,
            failure_ttl=86400,
        )
        logger.info(
            "[SRI POLL] Encolado job %s (attempt=%s/%s, delay=%ss)",
            job_id,
            attempt,
            max_attempts,
            delay_seconds,
        )
        return True
    except Exception as exc:
        logger.warning("[SRI POLL] No se pudo encolar poll para factura %s: %s", factura_id, exc)
        return False


def poll_autorizacion_factura(factura_id: int, empresa_id: int, attempt: int = 1, max_attempts: int = 240) -> None:
    """Consulta al SRI la autorización de una factura y re-encola cada 30s hasta estado final."""
    from inventario.models import Empresa, Factura
    from inventario.sri.integracion_django import SRIIntegration

    try:
        empresa = Empresa.objects.filter(id=empresa_id).first()
        if empresa is None:
            logger.warning("[SRI POLL] Empresa %s no existe", empresa_id)
            return

        try:
            from inventario.tenant.queryset import set_current_tenant

            try:
                set_current_tenant(empresa)
            except Exception as exc:
                logger.warning("[SRI POLL] No se pudo establecer tenant (empresa %s): %s", empresa_id, exc)
        except Exception:
            # Si no existe el mecanismo de tenant en algún entorno, continuar sin romper.
            pass

        factura = Factura.objects.filter(id=factura_id, empresa_id=empresa_id).first()
        if factura is None:
            logger.warning("[SRI POLL] Factura %s no existe en empresa %s", factura_id, empresa_id)
            return

        estado_actual = _normalize_state(getattr(factura, "estado_sri", None) or getattr(factura, "estado", None))

        # Si ya está final, no hacer nada.
        if estado_actual in FINAL_OK_STATES or estado_actual in {s.replace(" ", "_") for s in FINAL_FAIL_STATES}:
            logger.info("[SRI POLL] Factura %s ya final (%s)", factura_id, estado_actual)
            return

        integration = SRIIntegration(empresa=factura.empresa)
        integration.consultar_estado_factura(factura_id)

        factura.refresh_from_db(fields=["estado_sri", "estado", "numero_autorizacion", "fecha_autorizacion"])
        estado_nuevo = _normalize_state(getattr(factura, "estado_sri", None) or getattr(factura, "estado", None))

        if estado_nuevo in FINAL_OK_STATES:
            logger.info("[SRI POLL] Factura %s autorizada (%s)", factura_id, estado_nuevo)
            return

        if estado_nuevo in {s.replace(" ", "_") for s in FINAL_FAIL_STATES}:
            logger.info("[SRI POLL] Factura %s no autorizada/rechazada (%s)", factura_id, estado_nuevo)
            return

        # Todavía pendiente/recibida: re-encolar si quedan intentos.
        if attempt >= max_attempts:
            logger.warning(
                "[SRI POLL] Factura %s sigue pendiente (%s) y alcanzó max_attempts=%s",
                factura_id,
                estado_nuevo,
                max_attempts,
            )
            return

        # Por requerimiento: cada 30 segundos.
        enqueue_poll_autorizacion_factura(
            factura_id=factura_id,
            empresa_id=empresa_id,
            delay_seconds=30,
            attempt=attempt + 1,
            max_attempts=max_attempts,
        )

    except Exception as exc:
        logger.exception("[SRI POLL] Error en poll factura %s (attempt=%s/%s): %s", factura_id, attempt, max_attempts, exc)
        # Re-encolar con backoff básico de 30s si aún hay intentos.
        if attempt < max_attempts:
            enqueue_poll_autorizacion_factura(
                factura_id=factura_id,
                empresa_id=empresa_id,
                delay_seconds=30,
                attempt=attempt + 1,
                max_attempts=max_attempts,
            )


def enqueue_procesar_liquidacion_compra(
    *,
    liquidacion_id: int,
    empresa_id: int,
    delay_seconds: int = 5,
    attempt: int = 1,
    max_attempts: int = 720,
) -> bool:
    """Encola (o re-encola) el procesamiento SRI de una liquidación de compra en la cola `sri`.

    Reintenta agresivamente hasta estado final o max_attempts.
    """
    try:
        import django_rq

        queue = django_rq.get_queue("sri")
        job_id = f"sri_procesar_liquidacion_{empresa_id}_{liquidacion_id}"

        queue.enqueue_in(
            timedelta(seconds=max(0, int(delay_seconds))),
            procesar_liquidacion_compra_job,
            liquidacion_id,
            empresa_id,
            attempt,
            max_attempts,
            job_id=job_id,
            result_ttl=0,
            failure_ttl=86400,
        )
        logger.info(
            "[SRI LC] Encolado job %s (attempt=%s/%s, delay=%ss)",
            job_id,
            attempt,
            max_attempts,
            delay_seconds,
        )
        return True
    except Exception as exc:
        logger.warning("[SRI LC] No se pudo encolar liquidacion %s: %s", liquidacion_id, exc)
        return False


def procesar_liquidacion_compra_job(
    liquidacion_id: int,
    empresa_id: int,
    attempt: int = 1,
    max_attempts: int = 720,
) -> None:
    """Procesa liquidación y re-encola mientras esté pendiente/recibida/en procesamiento."""
    from inventario.models import Empresa
    from inventario.liquidacion_compra.models import LiquidacionCompra
    from inventario.liquidacion_compra.integracion_sri_liquidacion import IntegracionSRILiquidacion

    try:
        empresa = Empresa.objects.filter(id=empresa_id).first()
        if empresa is None:
            logger.warning("[SRI LC] Empresa %s no existe", empresa_id)
            return

        try:
            from inventario.tenant.queryset import set_current_tenant

            try:
                set_current_tenant(empresa)
            except Exception as exc:
                logger.warning("[SRI LC] No se pudo establecer tenant (empresa %s): %s", empresa_id, exc)
        except Exception:
            pass

        liquidacion = LiquidacionCompra.objects.filter(id=liquidacion_id, empresa_id=empresa_id).first()
        if liquidacion is None:
            logger.warning("[SRI LC] Liquidacion %s no existe en empresa %s", liquidacion_id, empresa_id)
            return

        estado_actual = _normalize_state(getattr(liquidacion, "estado_sri", None) or getattr(liquidacion, "estado", None))
        if estado_actual in FINAL_OK_STATES or estado_actual in {s.replace(" ", "_") for s in FINAL_FAIL_STATES}:
            logger.info("[SRI LC] Liquidacion %s ya final (%s)", liquidacion_id, estado_actual)
            return

        integracion = IntegracionSRILiquidacion(empresa)

        if estado_actual != "RECIBIDA":
            resultado = integracion.enviar_liquidacion(liquidacion)
        else:
            resultado = integracion.consultar_estado_actual(liquidacion)

        liquidacion.refresh_from_db(fields=["estado_sri", "estado", "numero_autorizacion", "fecha_autorizacion"])
        estado_nuevo = _normalize_state(getattr(liquidacion, "estado_sri", None) or getattr(liquidacion, "estado", None))

        if estado_nuevo in FINAL_OK_STATES:
            logger.info("[SRI LC] Liquidacion %s autorizada (%s)", liquidacion_id, estado_nuevo)
            return

        if estado_nuevo in {s.replace(" ", "_") for s in FINAL_FAIL_STATES}:
            logger.info("[SRI LC] Liquidacion %s no autorizada/rechazada (%s)", liquidacion_id, estado_nuevo)
            return

        if attempt >= max_attempts:
            logger.warning(
                "[SRI LC] Liquidacion %s sigue pendiente (%s) y alcanzó max_attempts=%s",
                liquidacion_id,
                estado_nuevo,
                max_attempts,
            )
            return

        enqueue_procesar_liquidacion_compra(
            liquidacion_id=liquidacion_id,
            empresa_id=empresa_id,
            delay_seconds=5,
            attempt=attempt + 1,
            max_attempts=max_attempts,
        )

    except Exception as exc:
        logger.exception("[SRI LC] Error procesando liquidacion %s (attempt=%s/%s): %s", liquidacion_id, attempt, max_attempts, exc)
        if attempt < max_attempts:
            enqueue_procesar_liquidacion_compra(
                liquidacion_id=liquidacion_id,
                empresa_id=empresa_id,
                delay_seconds=5,
                attempt=attempt + 1,
                max_attempts=max_attempts,
            )
