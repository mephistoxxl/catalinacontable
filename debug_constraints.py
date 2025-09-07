import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','sistema.settings')
import django
django.setup()
from django.db import connection

# List FK constraints on inventario_factura
sql = """
SELECT con.conname, pg_get_constraintdef(con.oid) as definition
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
WHERE nsp.nspname = 'public' AND rel.relname = 'inventario_factura' AND contype='f';
"""
with connection.cursor() as cur:
    cur.execute(sql)
    rows = cur.fetchall()
print('FK constraints on inventario_factura:')
for r in rows:
    print(r)
