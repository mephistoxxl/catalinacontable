"""
Servicio de envío de correos electrónicos
Maneja el envío de credenciales de acceso a nuevas empresas
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


def enviar_credenciales_nueva_empresa(empresa, usuario, password_temporal, email_destino=None):
    """
    Envía un correo electrónico con las credenciales de acceso
    a una nueva empresa creada desde el admin.
    
    Args:
        empresa: Instancia del modelo Empresa
        usuario: Instancia del modelo Usuario
        password_temporal: Contraseña temporal generada (string plano)
        email_destino: Email del destinatario (opcional, si no se pasa usa opciones)
    
    Returns:
        bool: True si el envío fue exitoso, False en caso contrario
    """
    try:
        print(f"\n{'='*80}")
        print(f"📧 ENVIANDO CORREO DE CREDENCIALES")
        print(f"Empresa: {empresa.razon_social}")
        print(f"Usuario: {usuario.username}")
        print(f"Email destino: {email_destino}")
        print(f"{'='*80}\n")
        
        # Datos para el template
        context = {
            'empresa_nombre': empresa.razon_social,
            'ruc': empresa.ruc,
            'usuario': usuario.username,
            'password': password_temporal,
            'url_login': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://www.catalinasoft-ec.com',
        }
        
        # Renderizar template HTML
        html_content = render_to_string('inventario/emails/credenciales_empresa.html', context)
        print(f"✅ Template HTML renderizado correctamente")
        
        # Crear email
        subject = f'¡Bienvenido {empresa.razon_social}!'
        from_email = settings.DEFAULT_FROM_EMAIL
        
        # Usar email_destino si se pasó, sino buscar en opciones
        if email_destino:
            to_email = email_destino
        else:
            to_email = empresa.opciones.first().correo if empresa.opciones.exists() else None
        
        if not to_email:
            print(f"❌ No se pudo enviar correo a empresa {empresa.ruc}: sin correo configurado")
            logger.warning(f"No se pudo enviar correo a empresa {empresa.ruc}: sin correo configurado")
            return False
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=f"Credenciales de acceso - Usuario: {usuario.username}, Contraseña: {password_temporal}",
            from_email=from_email,
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.mixed_subtype = 'related'  # Para imágenes embebidas
        
        # Adjuntar logo embebido
        try:
            from email.mime.image import MIMEImage
            import urllib.request
            
            logo_url = 'https://catalina-public-assets.s3.us-east-2.amazonaws.com/Logo+PNG+-+Catalina.png'
            print(f"🔍 Descargando logo desde: {logo_url}")
            
            with urllib.request.urlopen(logo_url, timeout=10) as response:
                logo_data = response.read()
                print(f"✅ Logo descargado: {len(logo_data)} bytes")
                
                logo_img = MIMEImage(logo_data)
                logo_img.add_header('Content-ID', '<logo-catalina>')
                logo_img.add_header('Content-Disposition', 'inline', filename='logo.png')
                email.attach(logo_img)
                print(f"✅ Logo embebido adjuntado")
        except Exception as e:
            print(f"⚠️ Error adjuntando logo: {e}")
            logger.warning(f"Error adjuntando logo al email de credenciales: {e}")
        
        print(f"📨 Enviando correo a: {to_email}")
        print(f"De: {from_email}")
        print(f"Asunto: {subject}")
        
        # Enviar
        email.send(fail_silently=False)
        print(f"✅ Correo de credenciales enviado exitosamente!")
        logger.info(f"✅ Correo de credenciales enviado a {to_email} para empresa {empresa.ruc}")
        return True
        
    except Exception as e:
        print(f"❌ ERROR enviando correo: {str(e)}")
        import traceback
        traceback.print_exc()
        logger.error(f"❌ Error enviando correo de credenciales a empresa {empresa.ruc}: {str(e)}")
        return False
