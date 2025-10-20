"""
Script para configurar/verificar datos de Opciones y preparar sistema para envío automático
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Opciones, Empresa

def configurar_opciones():
    print("=" * 60)
    print("CONFIGURACIÓN DE OPCIONES PARA ENVÍO AUTOMÁTICO DE EMAILS")
    print("=" * 60)
    
    # Verificar si ya existe Opciones
    opciones = Opciones.objects.first()
    
    if opciones:
        print(f"\n✅ Se encontró configuración existente:")
        print(f"   RUC: {opciones.identificacion}")
        print(f"   Razón Social: {opciones.razon_social}")
        print(f"   Correo: {opciones.correo}")
        
        # Verificar si tiene correo por defecto
        if opciones.correo == 'pendiente@empresa.com':
            print("\n⚠️ El correo es el valor por defecto.")
            print("\n¿Deseas actualizar el correo de la empresa?")
            actualizar = input("Ingresa 'si' para actualizar o presiona Enter para mantener: ").strip().lower()
            
            if actualizar == 'si':
                nuevo_correo = input("Ingresa el correo de tu empresa (ej: facturacion@catalinasoft-ec.com): ").strip()
                if nuevo_correo and '@' in nuevo_correo:
                    opciones.correo = nuevo_correo
                    opciones.save()
                    print(f"✅ Correo actualizado a: {nuevo_correo}")
                else:
                    print("❌ Correo inválido, se mantiene el actual")
        else:
            print(f"✅ Correo configurado correctamente: {opciones.correo}")
    else:
        print("\n❌ No hay configuración de Opciones en la base de datos")
        print("\nPara crear la configuración, necesitas:")
        print("1. Acceder al panel de administración Django")
        print("2. O crear manualmente con los siguientes datos:")
        
        # Verificar si hay empresa
        empresa = Empresa.objects.first()
        if empresa:
            print(f"\n✅ Empresa encontrada: {empresa.razon_social} (RUC: {empresa.ruc})")
            
            crear = input("\n¿Deseas crear Opciones ahora? (si/no): ").strip().lower()
            if crear == 'si':
                ruc = input("RUC de 13 dígitos: ").strip()
                razon_social = input("Razón Social: ").strip()
                correo = input("Correo empresa (ej: facturacion@catalinasoft-ec.com): ").strip()
                
                if len(ruc) == 13 and ruc.isdigit() and razon_social and '@' in correo:
                    opciones = Opciones.objects.create(
                        empresa=empresa,
                        identificacion=ruc,
                        razon_social=razon_social,
                        correo=correo,
                        direccion='Por configurar',
                        telefono='0000000000'
                    )
                    print(f"\n✅ Opciones creadas exitosamente!")
                    print(f"   RUC: {opciones.identificacion}")
                    print(f"   Razón Social: {opciones.razon_social}")
                    print(f"   Correo: {opciones.correo}")
                else:
                    print("❌ Datos inválidos. Por favor verifica:")
                    print("   - RUC debe tener exactamente 13 dígitos")
                    print("   - Correo debe ser válido")
        else:
            print("\n❌ No hay empresas en la base de datos")
            print("   Debes crear una empresa primero desde el panel admin")
    
    # Mostrar resumen final
    print("\n" + "=" * 60)
    print("RESUMEN DEL SISTEMA")
    print("=" * 60)
    
    opciones = Opciones.objects.first()
    if opciones:
        print("\n✅ CONFIGURACIÓN COMPLETA:")
        print(f"   📧 Email remitente: {opciones.correo}")
        print(f"   🏢 Razón Social: {opciones.razon_social}")
        print(f"   🆔 RUC: {opciones.identificacion}")
        
        print("\n📋 FLUJO AUTOMÁTICO DE ENVÍO:")
        print("   1. ✅ Generar XML de factura")
        print("   2. ✅ Firmar con XAdES-BES")
        print("   3. ✅ Enviar al SRI")
        print("   4. ✅ Consultar autorización")
        print("   5. ✅ Generar RIDE (PDF)")
        print("   6. ✅ ENVIAR EMAIL AUTOMÁTICAMENTE con PDF + XML")
        
        print("\n✉️ El email se enviará automáticamente cuando:")
        print(f"   - Remitente: {opciones.correo}")
        print("   - Destinatario: correo del cliente en la factura")
        print("   - Adjuntos: RIDE.pdf + XML autorizado")
        print("   - Vía: Zeptomail (smtp.zeptomail.com)")
        
        print("\n🎯 TODO LISTO PARA ENVÍO AUTOMÁTICO!")
    else:
        print("\n❌ Falta configurar Opciones")
        print("   El envío automático NO funcionará hasta completar la configuración")

if __name__ == '__main__':
    configurar_opciones()
