"""
Script de prueba para verificar configuración de email con Zeptomail
Ejecutar con: python test_email_config.py
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from django.core.mail import EmailMessage
from django.conf import settings

def test_email_configuration():
    """Prueba la configuración de email"""
    print("=" * 60)
    print("VERIFICACIÓN DE CONFIGURACIÓN DE EMAIL")
    print("=" * 60)
    
    # Mostrar configuración actual
    print(f"\n📧 Backend: {settings.EMAIL_BACKEND}")
    print(f"🌐 Host: {settings.EMAIL_HOST}")
    print(f"🔌 Puerto: {settings.EMAIL_PORT}")
    print(f"🔒 TLS: {settings.EMAIL_USE_TLS}")
    print(f"🔐 SSL: {settings.EMAIL_USE_SSL}")
    print(f"👤 Usuario: {settings.EMAIL_HOST_USER}")
    print(f"🔑 Password configurado: {'✅ Sí' if settings.EMAIL_HOST_PASSWORD else '❌ No'}")
    print(f"📨 From Email: {settings.DEFAULT_FROM_EMAIL}")
    
    # Verificar campos requeridos
    print("\n" + "=" * 60)
    print("VALIDACIÓN DE CONFIGURACIÓN")
    print("=" * 60)
    
    errores = []
    
    if not settings.EMAIL_HOST_PASSWORD or settings.EMAIL_HOST_PASSWORD == 'tu-api-key-aqui':
        errores.append("❌ EMAIL_HOST_PASSWORD no configurado o es valor por defecto")
    else:
        print("✅ EMAIL_HOST_PASSWORD configurado")
    
    if settings.EMAIL_HOST_USER == 'emailapikey':
        print("✅ EMAIL_HOST_USER correcto para Zeptomail")
    else:
        errores.append(f"⚠️ EMAIL_HOST_USER debería ser 'emailapikey' para Zeptomail (actual: {settings.EMAIL_HOST_USER})")
    
    if settings.EMAIL_HOST == 'smtp.zeptomail.com':
        print("✅ EMAIL_HOST correcto para Zeptomail")
    else:
        errores.append(f"❌ EMAIL_HOST incorrecto (actual: {settings.EMAIL_HOST})")
    
    if settings.EMAIL_PORT == 587:
        print("✅ EMAIL_PORT correcto (587)")
    else:
        errores.append(f"⚠️ EMAIL_PORT debería ser 587 (actual: {settings.EMAIL_PORT})")
    
    if settings.EMAIL_USE_TLS:
        print("✅ EMAIL_USE_TLS activado")
    else:
        errores.append("❌ EMAIL_USE_TLS debe estar en True")
    
    if not settings.EMAIL_USE_SSL:
        print("✅ EMAIL_USE_SSL desactivado (correcto para puerto 587)")
    else:
        errores.append("⚠️ EMAIL_USE_SSL debe estar en False para puerto 587")
    
    # Verificar modelo Opciones
    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE DATOS EN BASE DE DATOS")
    print("=" * 60)
    
    from inventario.models import Opciones, Cliente
    
    opciones = Opciones.objects.first()
    if opciones:
        print(f"\n✅ Opciones encontradas:")
        print(f"   - RUC: {opciones.identificacion}")
        print(f"   - Razón Social: {opciones.razon_social}")
        print(f"   - Correo: {opciones.correo}")
        
        if opciones.correo == 'pendiente@empresa.com':
            errores.append("⚠️ El correo en Opciones es el valor por defecto. Actualízalo con el correo real de tu empresa.")
    else:
        errores.append("❌ No hay registros en Opciones. Debes configurar los datos de tu empresa primero.")
    
    clientes = Cliente.objects.all()
    print(f"\n📋 Clientes en base de datos: {clientes.count()}")
    if clientes.exists():
        cliente_con_correo = clientes.exclude(correo='').first()
        if cliente_con_correo:
            print(f"   ✅ Ejemplo: {cliente_con_correo.razon_social} - {cliente_con_correo.correo}")
        else:
            errores.append("⚠️ Ningún cliente tiene correo configurado")
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    
    if errores:
        print("\n⚠️ SE ENCONTRARON LOS SIGUIENTES PROBLEMAS:\n")
        for error in errores:
            print(f"   {error}")
        print("\n❌ El envío de emails NO funcionará correctamente hasta resolver estos problemas.")
        return False
    else:
        print("\n✅ ¡Configuración correcta! El sistema está listo para enviar emails.")
        print("\n📝 PRÓXIMOS PASOS:")
        print("   1. Al enviar factura al SRI, se generará automáticamente el email")
        print("   2. El email incluirá el RIDE (PDF) y el XML autorizado")
        print("   3. Se enviará al correo del cliente registrado en la factura")
        return True

if __name__ == '__main__':
    test_email_configuration()
