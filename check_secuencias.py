import psycopg2
conn = psycopg2.connect(dbname='catalina_db', user='postgres', password='asebit0512', host='localhost')
cur = conn.cursor()

# Ver tabla secuencias
print("=== TABLA inventario_secuencia ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventario_secuencia' ORDER BY column_name")
cols = [r[0] for r in cur.fetchall()]
print(f"Columnas: {cols}")

print("\n=== SECUENCIAS (todas) ===")
cur.execute("SELECT * FROM inventario_secuencia LIMIT 10")
for row in cur.fetchall():
    print(f"  {row}")

# Ver si hay alguna secuencia con establecimiento=001, punto_emision=999
print("\n=== SECUENCIA con 001-999 ===")
cur.execute("SELECT * FROM inventario_secuencia WHERE establecimiento = '001' AND punto_emision = '999'")
for row in cur.fetchall():
    print(f"  {row}")

conn.close()
