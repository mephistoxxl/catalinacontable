#!/usr/bin/env python
import os
import django
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')

def create_database():
    """Crear la base de datos sisfact_db en PostgreSQL"""
    print("1️⃣ Creando base de datos PostgreSQL...")
    
    try:
        # Conectar a PostgreSQL como superusuario
        conn = psycopg2.connect(
            host='localhost',
            port='5434',
            user='postgres',
            password='asebit0512DELL*',
            database='postgres'  # BD por defecto
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Verificar si la BD ya existe
        cursor.execute("SELECT 1 FROM pg_database WHERE datname='sisfact_db'")
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute("CREATE DATABASE sisfact_db")
            print("   ✅ Base de datos 'sisfact_db' creada")
        else:
            print("   ℹ️  Base de datos 'sisfact_db' ya existe")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Error creando base de datos: {e}")
        print("   📝 Verifica que PostgreSQL esté ejecutándose y las credenciales sean correctas")
        return False

def migrate_to_postgresql():
    """Ejecutar la migración completa"""
    print("=== MIGRACIÓN SQLITE → POSTGRESQL ===\n")
    
    # Paso 1: Crear base de datos
    if not create_database():
        return False
    
    # Paso 2: Cambiar configuración a PostgreSQL
    print("2️⃣ Configurando Django para PostgreSQL...")
    os.environ['USE_POSTGRESQL'] = 'true'
    django.setup()
    
    # Paso 3: Verificar conexión
    print("3️⃣ Verificando conexión...")
    try:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"   ✅ Conectado a: {version}")
    except Exception as e:
        print(f"   ❌ Error de conexión: {e}")
        return False
    
    # Paso 4: Ejecutar migraciones
    print("4️⃣ Ejecutando migraciones...")
    from django.core.management import execute_from_command_line
    try:
        execute_from_command_line(['manage.py', 'migrate'])
        print("   ✅ Migraciones completadas")
    except Exception as e:
        print(f"   ❌ Error en migraciones: {e}")
        return False
    
    # Paso 5: Verificar backup
    if not os.path.exists('backup_sqlite_data.json'):
        print("   ❌ No se encontró backup_sqlite_data.json")
        print("   📝 Ejecuta primero: python backup_sqlite.py")
        return False
    
    # Paso 6: Importar datos
    print("5️⃣ Importando datos desde SQLite...")
    try:
        execute_from_command_line(['manage.py', 'loaddata', 'backup_sqlite_data.json'])
        print("   ✅ Datos importados exitosamente")
    except Exception as e:
        print(f"   ❌ Error importando datos: {e}")
        print("   💡 Algunos datos podrían ya existir, esto es normal")
    
    # Paso 7: Verificar datos
    print("6️⃣ Verificando migración...")
    from inventario.models import Usuario, Empresa, Cliente, Factura
    
    print(f"   Usuarios: {Usuario.objects.count()}")
    print(f"   Empresas: {Empresa.objects.count()}")
    print(f"   Clientes: {Cliente.objects.count()}")
    print(f"   Facturas: {Factura.objects.count()}")
    
    print("\n✅ MIGRACIÓN COMPLETADA EXITOSAMENTE!")
    print("📝 Para hacer permanente el cambio, edita .env:")
    print("   USE_POSTGRESQL=true")
    
    return True

if __name__ == "__main__":
    success = migrate_to_postgresql()
    if not success:
        print("\n❌ Migración falló")
        print("📋 Verifica:")
        print("   1. PostgreSQL está ejecutándose")
        print("   2. Credenciales correctas en .env")
        print("   3. Existe backup_sqlite_data.json")
