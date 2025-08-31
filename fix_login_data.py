#!/usr/bin/env python
import os
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Usuario, Empresa

def main():
    print("=== CREANDO EMPRESA DE PRUEBA ===")
    
    # Crear empresa si no existe
    empresa, created = Empresa.objects.get_or_create(
        ruc='1234567890001',
        defaults={
            'razon_social': 'Empresa de Prueba SAS'
        }
    )
    
    if created:
        print(f"✅ Empresa creada: {empresa.razon_social}")
    else:
        print(f"ℹ️  Empresa ya existía: {empresa.razon_social}")
    
    # Asociar todos los usuarios con la empresa
    usuarios = Usuario.objects.all()
    for usuario in usuarios:
        usuario.empresas.add(empresa)
        usuario.save()
        print(f"✅ Usuario {usuario.username} asociado con {empresa.razon_social}")
    
    print("\n=== VERIFICACIÓN FINAL ===")
    
    for usuario in usuarios:
        empresas_usuario = usuario.empresas.all()
        print(f"Usuario: {usuario.username}")
        print(f"  Empresas: {[e.razon_social for e in empresas_usuario]}")
        print()

if __name__ == "__main__":
    main()
