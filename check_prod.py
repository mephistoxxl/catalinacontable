import psycopg2

conn = psycopg2.connect(
    dbname='catalina_db',
    user='postgres',
    password='asebit0512',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# Ver detalle de factura 92
cur.execute('SELECT * FROM inventario_detallefactura WHERE factura_id = 92')
cols = [desc[0] for desc in cur.description]
print("COLUMNAS:", cols)
rows = cur.fetchall()
print(f"\nDETALLES ({len(rows)}):")
for r in rows:
    print(dict(zip(cols, r)))

# Ver producto si existe
if rows:
    prod_id = rows[0][cols.index('producto_id')]
    if prod_id:
        cur.execute(f'SELECT * FROM inventario_producto WHERE id = {prod_id}')
        pcols = [desc[0] for desc in cur.description]
        prow = cur.fetchone()
        if prow:
            print(f"\nPRODUCTO:")
            print(dict(zip(pcols, prow)))
        else:
            print(f"\nPRODUCTO ID {prod_id} NO EXISTE")
    else:
        print("\nproducto_id es NULL")

conn.close()
