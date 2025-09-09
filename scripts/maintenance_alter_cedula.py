import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings')

try:
    import django
    django.setup()
except Exception as e:
    sys.stderr.write("Failed to setup Django: %s\n" % e)
    sys.exit(2)

from django.db import connection

SQL = "ALTER TABLE inventario_cliente ALTER COLUMN cedula TYPE varchar(13);"

def main():
    with connection.cursor() as c:
        c.execute(SQL)
    print('ALTER executed successfully')

if __name__ == '__main__':
    main()
