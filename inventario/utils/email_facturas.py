import os
import logging
from datetime import datetime
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.files.storage import default_storage
from django.contrib.staticfiles import finders
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

    # ✅ Obtener nombre comercial de Opciones
    from inventario.models import Opciones
    opciones = Opciones.objects.filter(empresa=factura.empresa).first()
    nombre_emisor = opciones.nombre_comercial if opciones and opciones.nombre_comercial and opciones.nombre_comercial != '[CONFIGURAR NOMBRE COMERCIAL]' else factura.empresa.razon_social

    context = {
        'factura': factura,
        'empresa': factura.empresa,
        'cliente': factura.cliente,
        'numero_autorizacion': factura.numero_autorizacion,
        'fecha_autorizacion': factura.fecha_autorizacion,
        'total': factura.monto_general,
        'nombre_emisor': nombre_emisor,
    }
    try:
        body_html = render_to_string('inventario/email/factura_autorizada.html', context)
    except Exception:
        # fallback con diseño profesional
        body_html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Factura Autorizada</title>
</head>
<body style="margin:0; padding:0; font-family: Arial, sans-serif; background-color:#f3f4f6;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f4f6; padding:20px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
          <!-- Header VERDE con logo -->
          <tr>
            <td style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding:40px 20px; text-align:center;">
              <img src="https://catalina-media-prod.s3.us-east-2.amazonaws.com/static/inventario/assets/logo/logo-catalina.png" alt="{nombre_emisor}" style="max-width: 150px; height: auto; margin-bottom: 15px; background:white; padding:10px; border-radius:8px;" />
              <h1 style="margin:0; font-size:28px; font-weight:700; color:#ffffff; letter-spacing:1px;">{nombre_emisor}</h1>
              <p style="margin:8px 0 0; font-size:14px; color:#ffffff; font-weight:300; letter-spacing:0.5px;">Factura Electrónica Autorizada</p>
            </td>
          </tr>
          
          <!-- Contenido -->
          <tr>
            <td style="padding:30px 40px;">
              <p style="margin:0 0 20px; font-size:16px; color:#1f2937; line-height:1.6;">
                ¡Estimado/a <strong>{factura.nombre_cliente}</strong>!
              </p>
              
              <p style="margin:0 0 20px; font-size:14px; color:#4b5563; line-height:1.6;">
                Su factura ha sido <strong style="color:#10b981;">AUTORIZADA</strong> exitosamente por el SRI. El documento es completamente válido.
              </p>
              
              <!-- Badge número factura -->
              <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding:12px 20px; border-radius:8px; display:inline-block; margin:10px 0;">
                <span style="color:white; font-weight:600; font-size:14px; letter-spacing:0.5px;">
                  📋 {factura.establecimiento}-{factura.punto_emision}-{factura.secuencia}
                </span>
              </div>
              
              <!-- Tabla de detalles -->
              <table width="100%" cellpadding="10" cellspacing="0" style="margin:20px 0; border:1px solid #e5e7eb; border-radius:8px; overflow:hidden;">
                <tr style="background-color:#f9fafb;">
                  <td style="font-weight:600; color:#374151; font-size:13px; border-bottom:1px solid #e5e7eb;">Emisor</td>
                  <td style="color:#1f2937; font-size:13px; border-bottom:1px solid #e5e7eb;">{nombre_emisor}</td>
                </tr>
                <tr style="background-color:#ffffff;">
                  <td style="font-weight:600; color:#374151; font-size:13px; border-bottom:1px solid #e5e7eb;">RUC</td>
                  <td style="color:#1f2937; font-size:13px; border-bottom:1px solid #e5e7eb;">{factura.empresa.ruc}</td>
                </tr>
                <tr style="background-color:#f9fafb;">
                  <td style="font-weight:600; color:#374151; font-size:13px; border-bottom:1px solid #e5e7eb;">Autorización</td>
                  <td style="color:#1f2937; font-size:13px; font-family:monospace; border-bottom:1px solid #e5e7eb;">{factura.numero_autorizacion}</td>
                </tr>
                <tr style="background-color:#ffffff;">
                  <td style="font-weight:600; color:#374151; font-size:13px; border-bottom:1px solid #e5e7eb;">Fecha autorización</td>
                  <td style="color:#1f2937; font-size:13px; border-bottom:1px solid #e5e7eb;">{factura.fecha_autorizacion}</td>
                </tr>
                <tr style="background-color:#f0fdf4;">
                  <td style="font-weight:700; color:#047857; font-size:14px;">💰 Total</td>
                  <td style="font-weight:700; color:#047857; font-size:16px;">${factura.monto_general}</td>
                </tr>
              </table>
              
              <!-- Archivos adjuntos -->
              <div style="background-color:#eff6ff; border-left:4px solid #3b82f6; padding:15px; margin:20px 0; border-radius:4px;">
                <p style="margin:0 0 8px; font-size:14px; color:#1e40af; font-weight:600;">📎 Archivos adjuntos:</p>
                <ul style="margin:0; padding-left:20px; color:#1f2937; font-size:13px;">
                  <li>XML autorizado (estructura del comprobante)</li>
                  <li>RIDE en PDF (representación impresa)</li>
                </ul>
              </div>
              
              <p style="margin:20px 0 0; font-size:14px; color:#4b5563; line-height:1.6;">
                Gracias por su preferencia. 🙏
              </p>
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td style="background-color:#f9fafb; padding:20px 40px; border-top:1px solid #e5e7eb;">
              <p style="margin:0 0 5px; font-size:12px; color:#6b7280; text-align:center;">
                Este es un correo automático, por favor no responder.
              </p>
              <p style="margin:0; font-size:12px; color:#9ca3af; text-align:center;">
                {nombre_emisor}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
        """

    email = EmailMessage(
        subject=subject,
        body=body_html,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
        to=[correo_cliente],
        cc=cc_list,
    )
    email.content_subtype = 'html'
    
    # Adjuntar logo embebido para que se vea en el email
    try:
        from email.mime.image import MIMEImage

        logo_path = finders.find('inventario/assets/logo/logo-catalina.png')

        if logo_path:
            with open(logo_path, 'rb') as logo_file:
                logo_data = logo_file.read()
                logo_img = MIMEImage(logo_data)
                logo_img.add_header('Content-ID', '<logo-catalina>')
                logo_img.add_header('Content-Disposition', 'inline', filename='logo.png')
                email.attach(logo_img)
                logger.info(f"✅ Logo embebido adjuntado correctamente desde: {logo_path}")
        else:
            logger.warning("⚠️ No se pudo encontrar el logo estático para adjuntar")
    except Exception as e:
        logger.warning(f"Error general adjuntando logo embebido: {e}")
    
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
