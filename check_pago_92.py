import psycopg2
conn = psycopg2.connect(dbname='catalina_db', user='postgres', password='asebit0512', host='localhost')
cur = conn.cursor()

print("=== FORMA DE PAGO DE FACTURA 92 ===")
cur.execute("""
SELECT fp.id, fp.factura_id, fp.forma_pago, fp.total, fp.plazo, fp.unidad_tiempo, fp.caja_id, fp.empresa_id
FROM inventario_formapago fp
WHERE fp.factura_id = 92
""")
cols = ['id', 'factura_id', 'forma_pago', 'total', 'plazo', 'unidad_tiempo', 'caja_id', 'empresa_id']
for row in cur.fetchall():
    for i, col in enumerate(cols):
        print(f"  {col}: {row[i]}")

# Ver la caja si existe
print("\n=== CAJAS DISPONIBLES ===")
cur.execute("SELECT id, descripcion FROM inventario_caja WHERE activo = true AND empresa_id = 2")
for row in cur.fetchall():
    print(f"  id={row[0]}, descripcion='{row[1]}'")

conn.close()
