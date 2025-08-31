#!/usr/bin/env python
import os
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Usuario, Empresa

def main():
    print("=== VERIFICACIÓN DE DATOS PARA LOGIN ===")
    
    # Verificar usuarios
    usuarios = Usuario.objects.all()
    print(f"\nUsuarios en la base de datos: {usuarios.count()}")
    
    for usuario in usuarios[:5]:  # Solo mostrar primeros 5
        print(f"- Username: {usuario.username}")
        print(f"  Nombre: {usuario.first_name}")
        print(f"  Email: {usuario.email}")
        print(f"  Activo: {usuario.is_active}")
        empresas_usuario = usuario.empresas.all()
        print(f"  Empresas: {[e.razon_social for e in empresas_usuario]}")
        print()
    
    # Verificar empresas
    empresas = Empresa.objects.all()
    print(f"Empresas en la base de datos: {empresas.count()}")
    
    for empresa in empresas[:5]:  # Solo mostrar primeras 5
        print(f"- ID: {empresa.id}")
        print(f"  Razón Social: {empresa.razon_social}")
        print(f"  RUC: {empresa.ruc}")
        usuarios_empresa = empresa.usuario_set.all()
        print(f"  Usuarios: {[u.username for u in usuarios_empresa]}")
        print()

if __name__ == "__main__":
    main()
