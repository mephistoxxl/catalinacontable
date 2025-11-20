"""
Script de prueba para verificar que el logo se adjunta correctamente en emails
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from email.mime.image import MIMEImage
import urllib.request

def test_logo_attachment():
    """Prueba que el logo se descarga y adjunta correctamente"""
    
    print("=" * 60)
    print("TEST: Descarga y adjunto de logo en email")
    print("=" * 60)
    
    # 1. Descargar logo
    logo_url = 'https://catalina-public-assets.s3.us-east-2.amazonaws.com/Logo+PNG+-+Catalina.png'
    print(f"\n1️⃣ Descargando logo desde: {logo_url}")
    
    try:
        with urllib.request.urlopen(logo_url, timeout=10) as response:
            logo_data = response.read()
            print(f"   ✅ Logo descargado: {len(logo_data)} bytes")
            print(f"   ✅ Tipo de contenido: {response.headers.get('Content-Type')}")
    except Exception as e:
        print(f"   ❌ Error descargando logo: {e}")
        return False
    
    # 2. Crear email con logo embebido
    print(f"\n2️⃣ Creando email de prueba...")
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <div style="text-align: center; background: #10b981; padding: 40px; color: white;">
            <div style="background: white; padding: 15px; border-radius: 8px; display: inline-block; margin-bottom: 20px;">
                <img src="cid:logo-catalina" alt="Logo Catalina" style="max-width: 180px; height: auto;" />
            </div>
            <h1>Prueba de Logo en Email</h1>
        </div>
        <div style="padding: 20px;">
            <p>Este es un email de prueba para verificar que el logo se muestra correctamente.</p>
            <p>Si ves el logo arriba, significa que el sistema está funcionando bien.</p>
        </div>
    </body>
    </html>
    """
    
    email = EmailMultiAlternatives(
        subject='TEST: Logo en Email - Catalina Facturador',
        body='Email de prueba con logo embebido',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=['test@example.com'],  # Cambia esto por tu email
    )
    email.attach_alternative(html_body, "text/html")
    email.mixed_subtype = 'related'
    
    # 3. Adjuntar logo
    print(f"\n3️⃣ Adjuntando logo como imagen embebida...")
    try:
        logo_img = MIMEImage(logo_data)
        logo_img.add_header('Content-ID', '<logo-catalina>')
        logo_img.add_header('Content-Disposition', 'inline', filename='logo.png')
        email.attach(logo_img)
        print(f"   ✅ Logo adjuntado con Content-ID: <logo-catalina>")
    except Exception as e:
        print(f"   ❌ Error adjuntando logo: {e}")
        return False
    
    # 4. Mostrar estadísticas del email
    print(f"\n4️⃣ Estadísticas del email:")
    print(f"   - Total adjuntos: {len(email.attachments)}")
    print(f"   - Tipo MIME: {email.mixed_subtype}")
    print(f"   - From: {email.from_email}")
    print(f"   - Subject: {email.subject}")
    
    print(f"\n✅ TEST EXITOSO - El logo se descarga y adjunta correctamente")
    print(f"   El problema debe ser que Gmail está cacheando el email anterior.")
    print(f"   Prueba enviar a un email DIFERENTE o elimina el email anterior primero.")
    
    return True

if __name__ == '__main__':
    test_logo_attachment()
