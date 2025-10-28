import os
import logging
from datetime import datetime
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.files.storage import default_storage
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_factura_autorizada_email(factura, xml_path: str, ride_path: str, copia_empresa=True):
    """Envía correo con XML autorizado y RIDE.

    Parámetros:
        factura: instancia de Factura (con cliente relacionado)
        xml_path (str): ruta absoluta o ruta storage al XML autorizado
        ride_path (str): ruta absoluta o ruta storage al PDF RIDE
        copia_empresa (bool): si True agrega correo de la empresa en CC

    Requisitos previos:
        - factura.estado_sri == 'AUTORIZADA'
        - xml_path y ride_path deben existir (en filesystem o S3)
    """
    if factura.estado_sri != 'AUTORIZADA':
        raise ValueError("Factura no está autorizada; no se debe enviar correo todavía")

    # Verificar que los archivos existan (compatibilidad con S3 y filesystem local)
    # Para S3, la ruta puede tener sufijos aleatorios, así que solo verificamos si podemos abrirlo
    xml_exists = False
    try:
        if os.path.isabs(xml_path):
            xml_exists = os.path.exists(xml_path)
        else:
            xml_exists = default_storage.exists(xml_path)
    except Exception:
        pass
    
    ride_exists = False
    try:
        if os.path.isabs(ride_path):
            ride_exists = os.path.exists(ride_path)
        else:
            ride_exists = default_storage.exists(ride_path)
    except Exception:
        pass
    
    if not xml_exists:
        logger.warning(f"XML no encontrado en: {xml_path}, intentando leer directamente...")
    if not ride_exists:
        logger.warning(f"RIDE no encontrado en: {ride_path}, intentando leer directamente...")

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
    
    # Leer y adjuntar archivos (compatible con S3 y filesystem local)
    try:
        logger.info(f"Intentando adjuntar XML desde: {xml_path}")
        if os.path.isabs(xml_path) and os.path.exists(xml_path):
            # Filesystem local
            logger.info(f"Leyendo XML desde filesystem local")
            with open(xml_path, 'rb') as f:
                xml_content = f.read()
        else:
            # S3 o storage backend
            logger.info(f"Leyendo XML desde storage (S3)")
            with default_storage.open(xml_path, 'rb') as f:
                xml_content = f.read()
        
        email.attach(os.path.basename(xml_path), xml_content, 'application/xml')
        logger.info(f"✅ XML adjuntado exitosamente: {os.path.basename(xml_path)} ({len(xml_content)} bytes)")
    except Exception as e:
        logger.error(f"❌ Error adjuntando XML: {e}")
        raise
    
    try:
        logger.info(f"Intentando adjuntar PDF desde: {ride_path}")
        if os.path.isabs(ride_path) and os.path.exists(ride_path):
            # Filesystem local
            logger.info(f"Leyendo PDF desde filesystem local")
            with open(ride_path, 'rb') as f:
                pdf_content = f.read()
        else:
            # S3 o storage backend
            logger.info(f"Leyendo PDF desde storage (S3)")
            with default_storage.open(ride_path, 'rb') as f:
                pdf_content = f.read()
        
        email.attach(os.path.basename(ride_path), pdf_content, 'application/pdf')
        logger.info(f"✅ PDF adjuntado exitosamente: {os.path.basename(ride_path)} ({len(pdf_content)} bytes)")
    except Exception as e:
        logger.error(f"❌ Error adjuntando PDF: {e}")
        raise

    logger.info(f"📧 Enviando email con {len(email.attachments)} adjuntos...")
    email.send(fail_silently=False)
    logger.info(f"✅ Correo de factura {factura.id} enviado exitosamente a {correo_cliente} (cc={cc_list})")
    return True
