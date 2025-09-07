#!/usr/bin/env python
import os
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Usuario, Empresa
from django.contrib.auth.hashers import make_password

def create_basic_user():
    print("=== CREANDO USUARIO BÁSICO EN POSTGRESQL ===")
    
    # Obtener la empresa
    try:
        empresa = Empresa.objects.get(ruc='1234567890001')
        print(f"✅ Empresa encontrada: {empresa.razon_social}")
    except Empresa.DoesNotExist:
        print("❌ Empresa no encontrada. Ejecuta primero: python fix_login_data.py")
        return
    
    # Crear usuario superadmin
    usuario, created = Usuario.objects.get_or_create(
        username='admin',
        defaults={
            'password': make_password('admin123'),  # Contraseña: admin123
            'email': 'admin@sisfact.com',
            'first_name': 'Admin',
            'last_name': '',
            'is_superuser': True,
            'is_staff': True,
            'is_active': True,
            'nivel': 2
        }
    )
    
    if created:
        print(f"✅ Usuario creado: {usuario.username}")
    else:
        print(f"ℹ️  Usuario ya existía: {usuario.username}")
    
    # Asociar usuario con empresa
    usuario.empresas.add(empresa)
    usuario.save()
    
    print(f"✅ Usuario {usuario.username} asociado con {empresa.razon_social}")
    
    # Verificar
    print("\n=== VERIFICACIÓN ===")
    print(f"Usuario: {usuario.username}")
    print(f"Email: {usuario.email}")
    print(f"Activo: {usuario.is_active}")
    print(f"Empresas: {[e.razon_social for e in usuario.empresas.all()]}")
    
    print("\n=== DATOS PARA LOGIN ===")
    print("Usuario: admin")
    print("Contraseña: admin123")
    print("Empresa: Empresa de Prueba SAS")

if __name__ == "__main__":
    create_basic_user()
