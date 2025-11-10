import smtplib
import ssl
from email.message import EmailMessage
import os
from dotenv import load_dotenv

# Cargar variables de .env
load_dotenv()

port = 587
smtp_server = os.getenv('EMAIL_HOST', 'smtp.zeptomail.com')
username = os.getenv('EMAIL_HOST_USER', 'emailapikey')
password = os.getenv('EMAIL_HOST_PASSWORD', '')
from_email = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@catalinasoft-ec.com')

print("=" * 60)
print("CONFIGURACIÓN CARGADA DESDE .env:")
print("=" * 60)
print(f"SMTP Server: {smtp_server}")
print(f"Port: {port}")
print(f"Username: {username}")
print(f"Password: {password[:20]}..." if password else "Password: (vacío)")
print(f"From Email: {from_email}")
print("=" * 60)

if not password:
    print("\n❌ ERROR: La contraseña está vacía!")
    print("Verifica que el archivo .env esté en el directorio correcto.")
    exit(1)

message = "Test email enviado exitosamente desde el sistema de facturación."
msg = EmailMessage()
msg['Subject'] = "Test Email - Sistema Facturación"
msg['From'] = from_email
msg['To'] = "camilo.pumalpa@gmail.com"
msg.set_content(message)

print("\n🔄 Intentando enviar email...")
try:
    with smtplib.SMTP(smtp_server, port) as server:
        server.set_debuglevel(1)  # Ver detalles de la conexión
        print("\n📡 Iniciando STARTTLS...")
        server.starttls()
        print("\n🔐 Intentando login...")
        server.login(username, password)
        print("\n📧 Enviando mensaje...")
        server.send_message(msg)
    print("\n✅ Email enviado exitosamente!")
except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ Error de autenticación SMTP:")
    print(f"   Código: {e.smtp_code}")
    print(f"   Mensaje: {e.smtp_error.decode() if isinstance(e.smtp_error, bytes) else e.smtp_error}")
    print("\n💡 Posibles soluciones:")
    print("   1. Verifica que la contraseña en .env sea correcta")
    print("   2. Verifica que el usuario sea 'emailapikey' (no tu email)")
    print("   3. Revisa tu cuenta de ZeptoMail para verificar el estado")
except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}")
    print(f"   Detalle: {str(e)}")
