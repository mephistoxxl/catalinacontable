"""
Script para actualizar el campo numero_autorizacion en la base de datos
Ejecutar con: python fix_db_campo.py
"""
import os
import psycopg2
from urllib.parse import urlparse

# Leer DATABASE_URL del archivo .env
def get_database_url():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    with open(env_path, 'r') as f:
        for line in f:
            if line.startswith('DATABASE_URL='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return None

# Conectar y ejecutar el ALTER TABLE
try:
    database_url = get_database_url()
    
    if not database_url:
        print("❌ No se encontró DATABASE_URL en .env")
        exit(1)
    
    # Parsear la URL de la base de datos
    url = urlparse(database_url)
    
    # Conectar a PostgreSQL
    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        database=url.path[1:]  # Quitar el / inicial
    )
    
    cursor = conn.cursor()
    
    print("🔌 Conectado a la base de datos")
    
    # Ejecutar el ALTER TABLE
    sql = "ALTER TABLE guia_remision ALTER COLUMN numero_autorizacion TYPE VARCHAR(49);"
    
    cursor.execute(sql)
    conn.commit()
    
    print("✅ Campo numero_autorizacion actualizado exitosamente a VARCHAR(49)")
    
    # Verificar el cambio
    cursor.execute("""
        SELECT column_name, data_type, character_maximum_length 
        FROM information_schema.columns 
        WHERE table_name = 'guia_remision' 
        AND column_name = 'numero_autorizacion';
    """)
    
    result = cursor.fetchone()
    print(f"✅ Verificación: {result[0]} - {result[1]}({result[2]})")
    
    cursor.close()
    conn.close()
    
    print("\n🎉 ¡Listo! Ahora las guías de remisión funcionarán correctamente")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nSi el error es sobre psycopg2, instálalo con:")
    print("pip install psycopg2-binary")
