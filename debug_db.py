import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','sistema.settings')
import django
django.setup()
from django.conf import settings
from django.db import connection
from inventario.models import Cliente
print('Engine:', settings.DATABASES['default']['ENGINE'])
print('Clientes ORM IDs:', list(Cliente.objects.values_list('id','identificacion')))
with connection.cursor() as cur:
    cur.execute('SELECT id, identificacion FROM inventario_cliente ORDER BY id LIMIT 50')
    rows = cur.fetchall()
print('Clientes RAW:', rows)
