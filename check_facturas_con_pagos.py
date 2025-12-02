import psycopg2
conn = psycopg2.connect(dbname='catalina_db', user='postgres', password='asebit0512', host='localhost')
cur = conn.cursor()

# Ver qué facturas tienen formas de pago
print("=== FACTURAS CON FORMAS DE PAGO ===")
cur.execute("""
SELECT f.id, f.establecimiento, f.punto_emision, f.secuencia, f.monto_general, 
       COUNT(fp.id) as num_pagos
FROM inventario_factura f
LEFT JOIN inventario_formapago fp ON fp.factura_id = f.id
GROUP BY f.id
HAVING COUNT(fp.id) > 0
ORDER BY f.id DESC
LIMIT 10
""")
for row in cur.fetchall():
    print(f"  Factura {row[0]}: {row[1]}-{row[2]}-{row[3]}, monto=${row[4]}, pagos={row[5]}")

# Ver formas de pago de alguna factura
print("\n=== FORMAS DE PAGO EJEMPLO ===")
cur.execute("""
SELECT fp.id, fp.factura_id, fp.forma_pago, fp.total, fp.plazo
FROM inventario_formapago fp
LIMIT 5
""")
for row in cur.fetchall():
    print(f"  id={row[0]}, factura_id={row[1]}, forma_pago={row[2]}, total={row[3]}, plazo={row[4]}")

conn.close()
