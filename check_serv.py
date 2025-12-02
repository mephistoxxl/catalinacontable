import psycopg2

conn = psycopg2.connect(
    dbname='catalina_db',
    user='postgres',
    password='asebit0512',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# Ver servicio ID 2
cur.execute('SELECT * FROM inventario_servicio WHERE id = 2')
cols = [d[0] for d in cur.description]
r = cur.fetchone()
print("SERVICIO ID 2:")
if r:
    for c, v in zip(cols, r):
        print(f"  {c}: {v}")
else:
    print("  NO EXISTE")

conn.close()
