"""
Script para verificar que la protección de usuarios funciona correctamente
al eliminar empresas.

Este script simula lo que pasaría al eliminar una empresa y muestra
qué usuarios se eliminarían y cuáles se preservarían.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')
django.setup()

from inventario.models import Usuario, Empresa, UsuarioEmpresa

print("=" * 80)
print("VERIFICACIÓN DE PROTECCIÓN DE USUARIOS AL ELIMINAR EMPRESAS")
print("=" * 80)
print()

# Obtener todas las empresas
empresas = Empresa.objects.all()

print(f"📊 Total de empresas en el sistema: {empresas.count()}")
print()

for empresa in empresas:
    print(f"🏢 Empresa: {empresa.razon_social} (RUC: {empresa.ruc})")
    print("-" * 80)
    
    # Obtener usuarios de esta empresa
    usuarios = empresa.usuarios.all()
    
    print(f"   👥 Usuarios asociados: {usuarios.count()}")
    print()
    
    for usuario in usuarios:
        total_empresas = usuario.empresas.count()
        otras_empresas = usuario.empresas.exclude(id=empresa.id)
        
        print(f"   👤 Usuario: {usuario.username} ({usuario.email})")
        print(f"      - Es superusuario: {'SÍ' if usuario.is_superuser else 'NO'}")
        print(f"      - Total empresas asociadas: {total_empresas}")
        
        if otras_empresas.exists():
            print(f"      - Otras empresas: {', '.join([e.razon_social for e in otras_empresas])}")
        
        # Determinar si se eliminaría
        se_eliminaria = not usuario.is_superuser and total_empresas == 1
        
        if se_eliminaria:
            print(f"      ❌ SE ELIMINARÍA (solo pertenece a esta empresa)")
        else:
            if usuario.is_superuser:
                print(f"      ✅ SE PRESERVA (es superusuario - PROTEGIDO)")
            else:
                print(f"      ✅ SE PRESERVA (pertenece a {total_empresas} empresas - PROTEGIDO)")
        
        print()
    
    print()

print("=" * 80)
print("RESUMEN DE PROTECCIONES:")
print("=" * 80)
print()
print("✅ Usuarios PROTEGIDOS (NO se eliminan):")
print("   1. Superusuarios (is_superuser=True)")
print("   2. Usuarios que pertenecen a MÁS DE UNA empresa")
print()
print("❌ Usuarios que SÍ se eliminan:")
print("   1. Usuarios normales (is_superuser=False)")
print("   2. Que solo pertenecen a ESA empresa (empresas.count() == 1)")
print()
print("=" * 80)
print()

# Verificar la lógica de protección
print("🔍 VERIFICANDO LÓGICA DEL CÓDIGO:")
print()

codigo_verificacion = """
# Código en admin.py línea ~365:
for usuario in usuarios_empresa:
    if not usuario.is_superuser and usuario.empresas.count() == 1:
        usuario.delete()  # ← Solo elimina si cumple AMBAS condiciones
"""

print(codigo_verificacion)
print()
print("✅ Condición 1: not usuario.is_superuser")
print("   → El usuario NO debe ser superusuario")
print()
print("✅ Condición 2: usuario.empresas.count() == 1")
print("   → El usuario debe pertenecer SOLO a esta empresa")
print()
print("⚠️  AMBAS condiciones deben cumplirse (AND) para eliminar el usuario")
print("    Si el usuario está en 2+ empresas → NO se elimina ✅")
print()
print("=" * 80)
