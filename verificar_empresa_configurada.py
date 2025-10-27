"""
Script de verificación: Comprueba si la empresa necesita configuración
Uso: python verificar_empresa_configurada.py
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Empresa, Opciones, Usuario
from inventario.views import necesita_configuracion

def verificar_empresa(ruc):
    """Verifica si una empresa necesita configuración"""
    print(f"\n{'='*60}")
    print(f"🔍 VERIFICANDO EMPRESA: {ruc}")
    print(f"{'='*60}\n")
    
    try:
        empresa = Empresa.objects.get(ruc=ruc)
        print(f"✅ Empresa encontrada: {empresa.razon_social}")
        print(f"   ID: {empresa.id}")
        print(f"   RUC: {empresa.ruc}")
        
        # Obtener opciones
        opciones = Opciones.objects.filter(empresa=empresa).first()
        
        if not opciones:
            print(f"\n❌ NO tiene registro de Opciones")
            print(f"   → Debe ir a Configuración General")
            return
        
        print(f"\n📋 DATOS DE CONFIGURACIÓN:")
        print(f"   Identificación: {opciones.identificacion}")
        print(f"   Razón Social: {opciones.razon_social}")
        print(f"   Nombre Comercial: {opciones.nombre_comercial}")
        print(f"   Email: {opciones.correo}")
        print(f"   Teléfono: {opciones.telefono}")
        print(f"   Dirección: {opciones.direccion_establecimiento[:50]}...")
        
        print(f"\n🔐 FIRMA ELECTRÓNICA:")
        if opciones.firma_electronica:
            print(f"   ✅ Firma cargada: {opciones.firma_electronica.name}")
            print(f"   ✅ Password configurado: {'Sí' if opciones.password_firma else 'No'}")
            if opciones.fecha_caducidad_firma:
                print(f"   📅 Fecha caducidad: {opciones.fecha_caducidad_firma}")
        else:
            print(f"   ❌ NO tiene firma electrónica cargada")
        
        print(f"\n🔍 VERIFICACIONES:")
        
        # Verificar valores por defecto
        checks = {
            'RUC no es 0000000000000': opciones.identificacion != '0000000000000',
            'Razón social configurada': '[CONFIGURAR' not in opciones.razon_social.upper(),
            'Nombre comercial configurado': '[CONFIGURAR' not in opciones.nombre_comercial.upper(),
            'Dirección configurada': '[CONFIGURAR' not in opciones.direccion_establecimiento.upper(),
            'Email configurado': opciones.correo != 'pendiente@empresa.com',
            'Teléfono configurado': opciones.telefono != '0000000000',
            'Tiene firma electrónica': bool(opciones.firma_electronica),
            'Tiene password de firma': bool(opciones.password_firma),
        }
        
        for check, passed in checks.items():
            icon = '✅' if passed else '❌'
            print(f"   {icon} {check}")
        
        # Resultado final
        necesita = necesita_configuracion(empresa)
        
        print(f"\n{'='*60}")
        if necesita:
            print(f"❌ RESULTADO: La empresa NECESITA CONFIGURACIÓN")
            print(f"   → Al hacer login, irá a Configuración General")
        else:
            print(f"✅ RESULTADO: La empresa está COMPLETAMENTE CONFIGURADA")
            print(f"   → Al hacer login, irá directo al Panel Principal")
        print(f"{'='*60}\n")
        
    except Empresa.DoesNotExist:
        print(f"❌ ERROR: No se encontró empresa con RUC {ruc}")
        print(f"   Empresas disponibles:")
        for emp in Empresa.objects.all()[:10]:
            print(f"   - {emp.ruc}: {emp.razon_social}")

def listar_empresas():
    """Lista todas las empresas y su estado de configuración"""
    print(f"\n{'='*80}")
    print(f"📊 LISTADO DE EMPRESAS Y SU ESTADO DE CONFIGURACIÓN")
    print(f"{'='*80}\n")
    
    empresas = Empresa.objects.all()
    
    if not empresas.exists():
        print("❌ No hay empresas registradas")
        return
    
    print(f"{'RUC':<15} {'Razón Social':<30} {'Estado':<20}")
    print(f"{'-'*15} {'-'*30} {'-'*20}")
    
    for empresa in empresas:
        necesita = necesita_configuracion(empresa)
        estado = "❌ Necesita config" if necesita else "✅ Configurada"
        razon = empresa.razon_social[:28] if len(empresa.razon_social) <= 30 else empresa.razon_social[:28] + "..."
        print(f"{empresa.ruc:<15} {razon:<30} {estado:<20}")
    
    print(f"\n{'='*80}\n")

def verificar_usuario(username):
    """Verifica un usuario y sus empresas"""
    print(f"\n{'='*60}")
    print(f"👤 VERIFICANDO USUARIO: {username}")
    print(f"{'='*60}\n")
    
    try:
        usuario = Usuario.objects.get(username=username)
        print(f"✅ Usuario encontrado: {usuario.first_name} {usuario.last_name}")
        print(f"   Email: {usuario.email}")
        print(f"   Nivel: {usuario.get_nivel_display()}")
        
        empresas = usuario.empresas.all()
        print(f"\n🏢 EMPRESAS ASOCIADAS: {empresas.count()}")
        
        if empresas.count() == 0:
            print(f"   ❌ Usuario no tiene empresas asociadas")
            print(f"   → Al hacer login, se creará una empresa automáticamente")
        else:
            for i, empresa in enumerate(empresas, 1):
                print(f"\n   {i}. {empresa.razon_social}")
                print(f"      RUC: {empresa.ruc}")
                necesita = necesita_configuracion(empresa)
                if necesita:
                    print(f"      ❌ Necesita configuración")
                else:
                    print(f"      ✅ Completamente configurada")
        
        print(f"\n{'='*60}\n")
        
    except Usuario.DoesNotExist:
        print(f"❌ ERROR: No se encontró usuario con username {username}")
        print(f"   Usuarios disponibles:")
        for usr in Usuario.objects.all()[:10]:
            print(f"   - {usr.username}: {usr.first_name} {usr.last_name}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Verificar configuración de empresas')
    parser.add_argument('--ruc', help='RUC de la empresa a verificar')
    parser.add_argument('--usuario', help='Username del usuario a verificar')
    parser.add_argument('--listar', action='store_true', help='Listar todas las empresas')
    
    args = parser.parse_args()
    
    if args.ruc:
        verificar_empresa(args.ruc)
    elif args.usuario:
        verificar_usuario(args.usuario)
    elif args.listar:
        listar_empresas()
    else:
        # Si no se especifica nada, mostrar ayuda
        print("\n" + "="*60)
        print("🔧 VERIFICADOR DE CONFIGURACIÓN DE EMPRESAS")
        print("="*60 + "\n")
        print("Uso:")
        print("  python verificar_empresa_configurada.py --ruc 1713959011001")
        print("  python verificar_empresa_configurada.py --usuario 1713959011001")
        print("  python verificar_empresa_configurada.py --listar")
        print("\nEjemplos:")
        print("  # Verificar empresa específica")
        print("  python verificar_empresa_configurada.py --ruc 1713959011001")
        print("\n  # Verificar usuario y sus empresas")
        print("  python verificar_empresa_configurada.py --usuario linaspumalpa3@gmail.com")
        print("\n  # Listar todas las empresas")
        print("  python verificar_empresa_configurada.py --listar")
        print("\n" + "="*60 + "\n")
        
        # Por defecto, listar empresas
        listar_empresas()
