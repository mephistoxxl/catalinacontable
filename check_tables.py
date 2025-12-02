import psycopg2
conn = psycopg2.connect(dbname='catalina_db', user='postgres', password='asebit0512', host='localhost')
cur = conn.cursor()

print("=== TABLAS CON 'secuen' O 'punto' ===")
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND (table_name LIKE '%secuen%' OR table_name LIKE '%punto%')")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\n=== TODAS LAS TABLAS INVENTARIO ===")
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'inventario_%' ORDER BY table_name")
for r in cur.fetchall():
    print(f"  {r[0]}")

conn.close()
