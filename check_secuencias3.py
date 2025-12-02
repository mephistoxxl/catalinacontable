import psycopg2
conn = psycopg2.connect(dbname='catalina_db', user='postgres', password='asebit0512', host='localhost')
cur = conn.cursor()

print("=== SECUENCIAS CON NOMBRES DE COLUMNAS ===")
cur.execute("""
SELECT id, descripcion, establecimiento, punto_emision, secuencial, empresa_id 
FROM inventario_secuencias 
WHERE establecimiento = '001' AND punto_emision = '999'
""")
for row in cur.fetchall():
    print(f"  id={row[0]}, desc='{row[1]}', est={row[2]}, punto={row[3]}, secuencial={row[4]}, empresa_id={row[5]}")

# La factura 92 tiene empresa_id = ?
print("\n=== FACTURA 92 empresa_id ===")
cur.execute("SELECT empresa_id FROM inventario_factura WHERE id = 92")
emp = cur.fetchone()[0]
print(f"  empresa_id: {emp}")

print(f"\n=== SECUENCIA de empresa {emp} con 001-999 ===")
cur.execute("""
SELECT id, descripcion, establecimiento, punto_emision, secuencial
FROM inventario_secuencias 
WHERE establecimiento = '001' AND punto_emision = '999' AND empresa_id = %s
""", (emp,))
for row in cur.fetchall():
    print(f"  id={row[0]}, desc='{row[1]}', est={row[2]}, punto={row[3]}, secuencial={row[4]}")

conn.close()
