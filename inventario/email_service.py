"""
Servicio de envío de correos electrónicos
Maneja el envío de credenciales de acceso a nuevas empresas
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


def enviar_credenciales_nueva_empresa(empresa, usuario, password_temporal):
    """
    Envía un correo electrónico con las credenciales de acceso
    a una nueva empresa creada desde el admin.
    
    Args:
        empresa: Instancia del modelo Empresa
        usuario: Instancia del modelo Usuario
        password_temporal: Contraseña temporal generada (string plano)
    
    Returns:
        bool: True si el envío fue exitoso, False en caso contrario
    """
    try:
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
        
        # Crear email
        subject = f'¡Bienvenido {empresa.razon_social}!'
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = empresa.opciones.first().correo if empresa.opciones.exists() else None
        
        if not to_email:
            logger.warning(f"No se pudo enviar correo a empresa {empresa.ruc}: sin correo configurado")
            return False
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=f"Credenciales de acceso - Usuario: {usuario.username}, Contraseña: {password_temporal}",
            from_email=from_email,
            to=[to_email]
        )
        email.attach_alternative(html_content, "text/html")
        
        # Enviar
        email.send(fail_silently=False)
        logger.info(f"✅ Correo de credenciales enviado a {to_email} para empresa {empresa.ruc}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error enviando correo de credenciales a empresa {empresa.ruc}: {str(e)}")
        return False
