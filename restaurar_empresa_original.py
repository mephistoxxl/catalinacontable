#!/usr/bin/env python
import os
import django
import json

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Empresa, Usuario, UsuarioEmpresa

def restaurar_empresa_original():
    print("=== RESTAURANDO EMPRESA ORIGINAL ===")
    
    # Leer el backup
    with open('backup_sqlite_data.json', 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    print(f"✅ Backup cargado: {len(backup_data)} registros encontrados")
    
    # Filtrar datos por modelo
    empresas_data = [item for item in backup_data if item['model'] == 'inventario.empresa']
    usuarios_data = [item for item in backup_data if item['model'] == 'inventario.usuario']
    
    print(f"📊 Empresas en backup: {len(empresas_data)}")
    print(f"👥 Usuarios en backup: {len(usuarios_data)}")
    
    # Eliminar empresa de prueba
    try:
        empresa_prueba = Empresa.objects.get(ruc='1234567890001')
        print(f"🗑️ Eliminando empresa de prueba: {empresa_prueba.razon_social}")
        empresa_prueba.delete()
    except Empresa.DoesNotExist:
        print("ℹ️ No hay empresa de prueba que eliminar")
    
    # Restaurar empresas originales
    for item in empresas_data:
        empresa_data = item['fields']
        empresa, created = Empresa.objects.get_or_create(
            ruc=empresa_data['ruc'],
            defaults={
                'razon_social': empresa_data['razon_social']
            }
        )
        
        if created:
            print(f"✅ Empresa restaurada: {empresa.razon_social}")
        else:
            print(f"ℹ️ Empresa ya existe: {empresa.razon_social}")
        
        print(f"   RUC: {empresa.ruc}")
        print(f"   Razón Social: {empresa.razon_social}")
    
    # Eliminar usuario admin de prueba
    try:
        admin_user = Usuario.objects.get(username='admin')
        print(f"🗑️ Eliminando usuario admin de prueba")
        admin_user.delete()
    except Usuario.DoesNotExist:
        print("ℹ️ No hay usuario admin de prueba que eliminar")
    
    # Restaurar usuarios originales
    print("\n=== RESTAURANDO USUARIOS ORIGINALES ===")
    for item in usuarios_data:
        usuario_data = item['fields']
        usuario, created = Usuario.objects.get_or_create(
            username=usuario_data['username'],
            defaults={
                'email': usuario_data['email'],
                'first_name': usuario_data['first_name'],
                'last_name': usuario_data['last_name'],
                'password': usuario_data['password'],  # Ya está hasheada
                'is_superuser': usuario_data.get('is_superuser', False),
                'is_staff': usuario_data.get('is_staff', False),
                'is_active': usuario_data.get('is_active', True),
                'nivel': usuario_data.get('nivel', 1),
                'last_login': usuario_data.get('last_login'),
                'date_joined': usuario_data.get('date_joined')
            }
        )
        
        if created:
            print(f"✅ Usuario restaurado: {usuario.username}")
        else:
            print(f"ℹ️ Usuario ya existe: {usuario.username}")
            # Actualizar contraseña si es necesario
            usuario.password = usuario_data['password']
            usuario.save()
            print(f"   Contraseña actualizada para: {usuario.username}")
        
        print(f"   Email: {usuario.email}")
        print(f"   Nombre: {usuario.first_name} {usuario.last_name}")
        print(f"   Superusuario: {usuario.is_superuser}")
    
    # Asociar usuarios con empresas (simplificado - todos los usuarios con todas las empresas)
    print("\n=== ASOCIANDO USUARIOS CON EMPRESAS ===")
    empresas = Empresa.objects.all()
    usuarios = Usuario.objects.all()
    
    for usuario in usuarios:
        for empresa in empresas:
            relacion, created = UsuarioEmpresa.objects.get_or_create(
                usuario=usuario,
                empresa=empresa
            )
            
            if created:
                print(f"✅ Relación creada: {usuario.username} -> {empresa.razon_social}")
    
    print("\n=== RESUMEN FINAL ===")
    empresas = Empresa.objects.all()
    usuarios = Usuario.objects.all()
    
    for empresa in empresas:
        print(f"🏢 Empresa: {empresa.razon_social} ({empresa.ruc})")
        usuarios_empresa = empresa.usuarios.all()
        for usuario in usuarios_empresa:
            print(f"   👤 Usuario: {usuario.username} ({usuario.email})")
    
    print("\n=== DATOS PARA LOGIN ===")
    for usuario in usuarios:
        if usuario.is_superuser:
            print(f"🔑 SUPERUSUARIO: {usuario.username}")
            print(f"   Email: {usuario.email}")
            print(f"   Nombre: {usuario.first_name} {usuario.last_name}")
            for empresa in empresas:
                print(f"   Empresa disponible: {empresa.razon_social}")

if __name__ == '__main__':
    restaurar_empresa_original()
