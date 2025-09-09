import os
import sys

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

SQL = (
    "BEGIN;"
    "TRUNCATE TABLE inventario_factura CASCADE;"
    "TRUNCATE TABLE inventario_cliente CASCADE;"
    "COMMIT;"
)

def main():
    if load_dotenv is not None:
        load_dotenv()

    import psycopg2
    dbname = os.getenv('DB_NAME', 'sisfact_db')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', 'postgres')
    host = os.getenv('DB_HOST', 'localhost')
    port = int(os.getenv('DB_PORT', '5432'))

    try:
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(SQL)
        conn.close()
        print('WIPED: inventario_factura, inventario_cliente (CASCADE)')
        return 0
    except Exception as e:
        sys.stderr.write(('ERROR: ' + str(e)).encode('ascii', 'ignore').decode('ascii') + '\n')
        return 1

if __name__ == '__main__':
    sys.exit(main())
