import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from django.conf import settings
from django.core.mail import send_mail

print("=" * 60)
print("CONFIGURACIÓN EMAIL ACTUAL:")
print("=" * 60)
print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
print(f"EMAIL_HOST_PASSWORD: {settings.EMAIL_HOST_PASSWORD[:20]}..." if settings.EMAIL_HOST_PASSWORD else "EMAIL_HOST_PASSWORD: (vacío)")
print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"EMAIL_USE_SSL: {settings.EMAIL_USE_SSL}")
print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
print("=" * 60)

# Intentar enviar email de prueba
print("\n🔄 Intentando enviar email de prueba...")
try:
    send_mail(
        subject='Test desde Django',
        message='Este es un email de prueba desde el sistema de facturación.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=['camilo.pumalpa@gmail.com'],
        fail_silently=False,
    )
    print("✅ Email enviado exitosamente!")
except Exception as e:
    print(f"❌ Error al enviar email: {type(e).__name__}")
    print(f"   Detalle: {str(e)}")
