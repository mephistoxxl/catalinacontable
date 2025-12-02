import psycopg2
conn = psycopg2.connect(dbname='catalina_db', user='postgres', password='asebit0512', host='localhost')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventario_factura' ORDER BY column_name")
print("=== COLUMNAS DE inventario_factura ===")
for r in cur.fetchall():
    print(f"  - {r[0]}")

# Ver datos de factura 92
print("\n=== FACTURA 92 ===")
cur.execute("""
SELECT id, establecimiento, punto_emision, secuencia,
       identificacion_cliente, nombre_cliente, 
       almacen_id
FROM inventario_factura WHERE id = 92
""")
row = cur.fetchone()
if row:
    cols = ['id', 'establecimiento', 'punto_emision', 'secuencia',
            'identificacion_cliente', 'nombre_cliente',
            'almacen_id']
    for i, col in enumerate(cols):
        print(f"  {col}: {row[i]}")

# Ver almacen
print("\n=== ALMACEN id=5 ===")
cur.execute("SELECT * FROM inventario_almacen WHERE id = 5")
row = cur.fetchone()
if row:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventario_almacen'")
    cols = [r[0] for r in cur.fetchall()]
    print(f"  cols: {cols}")
    cur.execute("SELECT * FROM inventario_almacen WHERE id = 5")
    row = cur.fetchone()
    print(f"  data: {row}")

# Ver cliente
print("\n=== COLUMNAS CLIENTE ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'inventario_cliente' ORDER BY column_name")
for r in cur.fetchall():
    print(f"  - {r[0]}")

print("\n=== CLIENTE de factura 92 ===")
cur.execute("SELECT cliente_id FROM inventario_factura WHERE id = 92")
cliente_id = cur.fetchone()[0]
print(f"  cliente_id en factura: {cliente_id}")

cur.execute("SELECT * FROM inventario_cliente WHERE id = %s", (cliente_id,))
row = cur.fetchone()
print(f"  data: {row}")

conn.close()
