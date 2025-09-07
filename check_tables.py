#!/usr/bin/env python
import psycopg2

def check_tables():
    conn = psycopg2.connect(
        host='localhost',
        port='5434',
        user='postgres',
        password='asebit0512DELL*',
        database='sisfact_db'
    )

    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)

    tables = cursor.fetchall()
    print('=== TABLAS CREADAS EN POSTGRESQL ===')
    for table in tables:
        print(f'- {table[0]}')

    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_tables()
