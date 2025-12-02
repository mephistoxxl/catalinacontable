import psycopg2

conn = psycopg2.connect(
    dbname='catalina_db',
    user='postgres',
    password='asebit0512',
    host='localhost',
    port='5432'
)
cur = conn.cursor()

# Ver factura 92 completa
cur.execute('''
    SELECT id, establecimiento, punto_emision, secuencia, 
           identificacion_cliente, nombre_cliente, 
           almacen_id, monto_general, concepto
    FROM inventario_factura 
    WHERE id = 92
''')
f = cur.fetchone()
print(f"FACTURA ID {f[0]}")
print(f"  Establecimiento: {f[1]}")
print(f"  Punto Emisión: {f[2]}")
print(f"  Secuencia: {f[3]}")
print(f"  Identificación: {f[4]}")
print(f"  Nombre: {f[5]}")
print(f"  Almacén ID: {f[6]}")
print(f"  Monto: {f[7]}")
print(f"  Concepto: {f[8]}")

# Ver detalles
cur.execute('''
    SELECT df.id, df.producto_id, df.cantidad, 
           df.precio_unitario, df.tarifa_iva,
           p.codigo, p.descripcion as prod_desc
    FROM inventario_detallefactura df
    LEFT JOIN inventario_producto p ON df.producto_id = p.id
    WHERE df.factura_id = 92
''')
print(f"\nDETALLES:")
for d in cur.fetchall():
    print(f"  ID {d[0]}:")
    print(f"    producto_id: {d[1]}")
    print(f"    cantidad: {d[2]}")
    print(f"    precio_unitario: {d[3]}")
    print(f"    tarifa_iva: {d[4]}")
    print(f"    producto.codigo: '{d[5]}'")
    print(f"    producto.descripcion: '{d[6]}'")

# Ver formas de pago
cur.execute('''
    SELECT forma_pago, total FROM inventario_formapago WHERE factura_id = 92
''')
print(f"\nFORMAS DE PAGO:")
for p in cur.fetchall():
    print(f"  {p[0]}: ${p[1]}")

conn.close()
