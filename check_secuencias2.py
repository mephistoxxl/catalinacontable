import psycopg2
conn = psycopg2.connect(dbname='catalina_db', user='postgres', password='asebit0512', host='localhost')
cur = conn.cursor()

print("=== COLUMNAS inventario_secuencias ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventario_secuencias' ORDER BY column_name")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\n=== SECUENCIAS (primeras 5) ===")
cur.execute("SELECT * FROM inventario_secuencias LIMIT 5")
for row in cur.fetchall():
    print(f"  {row}")

# Buscar secuencia que coincida con factura 92 (establecimiento=001, punto_emision=999)
print("\n=== SECUENCIA para 001-999 ===")
cur.execute("SELECT * FROM inventario_secuencias WHERE establecimiento = '001' AND punto_emision = '999'")
for row in cur.fetchall():
    print(f"  {row}")

conn.close()
