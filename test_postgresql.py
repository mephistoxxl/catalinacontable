#!/usr/bin/env python
import psycopg2
import sys

def test_connection(host='localhost', port='5432', user='postgres', password='postgres'):
    """Probar diferentes combinaciones de conexión"""
    
    # Lista de contraseñas comunes durante instalación
    passwords_to_try = [
        'postgres',
        '',  # Sin contraseña
        'admin',
        '123456',
        'password'
    ]
    
    if password not in passwords_to_try:
        passwords_to_try.insert(0, password)
    
    print("🔍 Probando conexión a PostgreSQL...")
    print(f"   Host: {host}")
    print(f"   Puerto: {port}")
    print(f"   Usuario: {user}")
    
    for pwd in passwords_to_try:
        try:
            print(f"\n🔑 Probando contraseña: {'(vacía)' if pwd == '' else '***'}")
            
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=pwd,
                database='postgres'
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            print(f"✅ CONEXIÓN EXITOSA!")
            print(f"   Versión: {version}")
            print(f"   Contraseña correcta: {'(vacía)' if pwd == '' else pwd}")
            
            return pwd
            
        except psycopg2.OperationalError as e:
            print(f"❌ Falló: {str(e)}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print("\n❌ NO SE PUDO CONECTAR A POSTGRESQL")
    print("📋 Posibles causas:")
    print("   1. PostgreSQL no está ejecutándose")
    print("   2. Puerto diferente (¿5433?)")
    print("   3. Contraseña diferente")
    print("   4. Usuario diferente")
    
    return None

if __name__ == "__main__":
    correct_password = test_connection()
    
    if correct_password is not None:
        print(f"\n📝 Actualiza tu .env con:")
        print(f"DB_PASSWORD={correct_password}")
        print("\nAhora puedes ejecutar: python full_migration.py")
    else:
        print("\n🔧 Para verificar el estado de PostgreSQL:")
        print("   - Busca 'Services' en Windows")
        print("   - Busca 'postgresql' y verifica que esté 'Running'")
        print("   - O reinicia el servicio")
