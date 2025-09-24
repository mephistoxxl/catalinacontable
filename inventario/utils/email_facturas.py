import os
import logging
from datetime import datetime
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_factura_autorizada_email(factura, xml_path: str, ride_path: str, copia_empresa=True):
    """Envía correo con XML autorizado y RIDE.

    Parámetros:
        factura: instancia de Factura (con cliente relacionado)
        xml_path (str): ruta absoluta al XML autorizado
        ride_path (str): ruta absoluta al PDF RIDE
        copia_empresa (bool): si True agrega correo de la empresa en CC

    Requisitos previos:
        - factura.estado_sri == 'AUTORIZADA'
        - xml_path y ride_path deben existir
    """
    if factura.estado_sri != 'AUTORIZADA':
        raise ValueError("Factura no está autorizada; no se debe enviar correo todavía")

    if not (xml_path and os.path.exists(xml_path)):
        raise FileNotFoundError(f"XML no encontrado: {xml_path}")
    if not (ride_path and os.path.exists(ride_path)):
        raise FileNotFoundError(f"RIDE no encontrado: {ride_path}")

    # Determinar correo cliente
    correo_cliente = getattr(factura.cliente, 'correo', None)
    if not correo_cliente:
        raise ValueError("El cliente no tiene correo registrado")

    # Determinar copia empresa
    cc_list = []
    if copia_empresa:
        correo_empresa = getattr(factura.empresa, 'correo', None)
        if correo_empresa and correo_empresa != correo_cliente:
            cc_list.append(correo_empresa)

    subject = f"Factura electrónica {factura.establecimiento}-{factura.punto_emision}-{factura.secuencia} AUTORIZADA"

    context = {
        'factura': factura,
        'empresa': factura.empresa,
        'cliente': factura.cliente,
        'numero_autorizacion': factura.numero_autorizacion,
        'fecha_autorizacion': factura.fecha_autorizacion,
        'total': factura.monto_general,
    }
    try:
        body_html = render_to_string('inventario/email/factura_autorizada.html', context)
    except Exception:
        # fallback simple
        body_html = (
            f"<p>Estimado(a) {factura.nombre_cliente},</p>"
            f"<p>Adjuntamos su factura electrónica autorizada.</p>"
            f"<p>Número de autorización: {factura.numero_autorizacion}</p>"
            f"<p>Total: {factura.monto_general}</p>"
            f"<p>Gracias por su compra.</p>"
        )

    email = EmailMessage(
        subject=subject,
        body=body_html,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
        to=[correo_cliente],
        cc=cc_list,
    )
    email.content_subtype = 'html'
    email.attach(os.path.basename(xml_path), open(xml_path, 'rb').read(), 'application/xml')
    email.attach(os.path.basename(ride_path), open(ride_path, 'rb').read(), 'application/pdf')

    email.send(fail_silently=False)
    logger.info(f"Correo de factura {factura.id} enviado a {correo_cliente} (cc={cc_list})")
    return True
