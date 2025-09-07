#!/usr/bin/env python
import psycopg2
import sys

def test_multiple_postgresql():
    """Probar diferentes puertos y versiones de PostgreSQL"""
    
    # Puertos comunes para múltiples versiones
    ports_to_try = ['5432', '5433', '5434', '5435']
    users_to_try = ['postgres']
    passwords_to_try = ['postgres', '', 'admin']
    
    print("🔍 Detectamos múltiples versiones de PostgreSQL")
    print("   Probando diferentes puertos y configuraciones...\n")
    
    for port in ports_to_try:
        print(f"🔌 Probando puerto {port}:")
        
        for user in users_to_try:
            for password in passwords_to_try:
                try:
                    print(f"   Usuario: {user}, Password: {'(vacía)' if password == '' else '***'}")
                    
                    conn = psycopg2.connect(
                        host='localhost',
                        port=port,
                        user=user,
                        password=password,
                        database='postgres',
                        connect_timeout=3
                    )
                    
                    cursor = conn.cursor()
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()[0]
                    
                    cursor.close()
                    conn.close()
                    
                    print(f"   ✅ CONEXIÓN EXITOSA!")
                    print(f"   Puerto: {port}")
                    print(f"   Usuario: {user}")
                    print(f"   Password: {password if password else '(vacía)'}")
                    print(f"   Versión: {version}")
                    
                    return port, user, password
                    
                except psycopg2.OperationalError as e:
                    if "timeout expired" in str(e):
                        print(f"   ❌ Timeout en puerto {port}")
                        break
                    elif "Connection refused" in str(e):
                        print(f"   ❌ Puerto {port} no responde")
                        break
                    else:
                        print(f"   ❌ Falló autenticación")
                except Exception as e:
                    print(f"   ❌ Error: {str(e)}")
        
        print()
    
    print("❌ NO SE PUDO CONECTAR A NINGUNA INSTANCIA")
    return None, None, None

if __name__ == "__main__":
    port, user, password = test_multiple_postgresql()
    
    if port:
        print(f"\n📝 Configuración encontrada:")
        print(f"   Puerto: {port}")
        print(f"   Usuario: {user}")
        print(f"   Password: {password}")
        
        print(f"\n📝 Actualiza tu .env con:")
        print(f"DB_PORT={port}")
        print(f"DB_USER={user}")
        print(f"DB_PASSWORD={password}")
        
        print(f"\nAhora ejecuta: python full_migration.py")
    else:
        print("\n🔧 Recomendaciones:")
        print("   1. Verifica que al menos un servicio PostgreSQL esté 'Running'")
        print("   2. Reinicia los servicios PostgreSQL")
        print("   3. Usa pgAdmin para verificar la conexión")
