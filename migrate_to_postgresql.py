#!/usr/bin/env python
"""
Script para migrar de SQLite a PostgreSQL en el proyecto SISFACT
"""
import os
import django
import sys

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')

def migrate_to_postgresql():
    print("=== MIGRACIÓN SQLITE → POSTGRESQL ===")
    
    # Verificar que tenemos el backup
    if not os.path.exists('backup_sqlite_data.json'):
        print("❌ Error: No se encontró backup_sqlite_data.json")
        print("   Ejecuta primero: python backup_sqlite.py")
        return False
    
    # Cambiar a PostgreSQL
    print("1️⃣ Configurando PostgreSQL...")
    os.environ['USE_POSTGRESQL'] = 'true'
    
    # Reinicializar Django con nueva configuración
    django.setup()
    
    # Verificar conexión a PostgreSQL
    try:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"   ✅ Conectado a PostgreSQL: {version}")
    except Exception as e:
        print(f"   ❌ Error conectando a PostgreSQL: {e}")
        print("   Asegúrate de que PostgreSQL esté ejecutándose")
        return False
    
    # Ejecutar migraciones
    print("2️⃣ Ejecutando migraciones...")
    os.system('python manage.py migrate')
    
    # Importar datos
    print("3️⃣ Importando datos...")
    import json
    from django.core.management import call_command
    
    try:
        call_command('loaddata', 'backup_sqlite_data.json')
        print("   ✅ Datos importados exitosamente")
    except Exception as e:
        print(f"   ❌ Error importando datos: {e}")
        return False
    
    # Verificar datos
    print("4️⃣ Verificando migración...")
    from inventario.models import Usuario, Empresa, Cliente
    
    print(f"   Usuarios: {Usuario.objects.count()}")
    print(f"   Empresas: {Empresa.objects.count()}")
    print(f"   Clientes: {Cliente.objects.count()}")
    
    print("\n✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
    print("   Para hacer permanente el cambio, edita .env:")
    print("   USE_POSTGRESQL=true")
    
    return True

def instructions():
    print("""
=== INSTRUCCIONES PARA MIGRAR A POSTGRESQL ===

OPCIÓN 1: Instalar PostgreSQL localmente
1. Descargar desde: https://www.postgresql.org/download/windows/
2. Instalar con usuario 'postgres' y contraseña 'postgres'
3. Ejecutar: python migrate_to_postgresql.py

OPCIÓN 2: Usar PostgreSQL con Docker
1. Instalar Docker Desktop
2. Ejecutar: docker run --name sisfact-postgres -e POSTGRES_DB=sisfact_db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:15
3. Ejecutar: python migrate_to_postgresql.py

OPCIÓN 3: Usar PostgreSQL en la nube (recomendado para pruebas)
1. Crear cuenta en https://www.elephantsql.com/ (gratis)
2. Obtener URL de conexión
3. Modificar .env con los datos de conexión
4. Ejecutar: python migrate_to_postgresql.py

Para volver a SQLite:
- Cambiar .env: USE_POSTGRESQL=false
""")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        instructions()
    else:
        # Verificar si PostgreSQL está disponible
        os.environ['USE_POSTGRESQL'] = 'true'
        try:
            django.setup()
            from django.db import connection
            connection.ensure_connection()
            migrate_to_postgresql()
        except Exception as e:
            print(f"❌ PostgreSQL no está disponible: {e}")
            print("\n📋 Ejecuta con --help para ver las opciones de instalación")
            instructions()
