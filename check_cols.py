import psycopg2

conn = psycopg2.connect(
    dbname='catalina_db',
    user='postgres',
    password='asebit0512',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# Ver columnas de detallefactura
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventario_detallefactura'")
print("Columnas de inventario_detallefactura:")
for r in cur.fetchall():
    print(f"  - {r[0]}")

conn.close()
