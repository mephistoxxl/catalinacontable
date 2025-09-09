import os
import sys

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

def main():
    # Load .env if available
    if load_dotenv is not None:
        load_dotenv()

    import psycopg2

    dbname = os.getenv('DB_NAME', 'sisfact_db')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', 'postgres')
    host = os.getenv('DB_HOST', 'localhost')
    port = int(os.getenv('DB_PORT', '5432'))

    sql = "ALTER TABLE inventario_cliente ALTER COLUMN cedula TYPE varchar(13);"

    try:
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print('ALTER OK')
        return 0
    except Exception as e:
        sys.stderr.write(('ERROR: ' + str(e)).encode('ascii', 'ignore').decode('ascii') + '\n')
        return 1

if __name__ == '__main__':
    sys.exit(main())
