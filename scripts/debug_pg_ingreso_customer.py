import os
import psycopg  # type: ignore

def connect_pg():
    host = os.getenv('PG_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
    port = int(os.getenv('PG_PORT', os.getenv('POSTGRES_PORT', '5433')))
    db = os.getenv('PG_DB', os.getenv('POSTGRES_DB', 'servicio_tecnico'))
    user = os.getenv('PG_USER', os.getenv('POSTGRES_USER', 'sepid'))
    pw = os.getenv('PG_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)

def main():
    os_ids = [1,15177,15208,15243]
    with connect_pg() as cn:
        with cn.cursor() as cur:
            for os_id in os_ids:
                cur.execute(
                    """
                    SELECT i.id, i.device_id, c.id, c.razon_social
                    FROM ingresos i JOIN devices d ON d.id=i.device_id JOIN customers c ON c.id=d.customer_id
                    WHERE i.id=%s
                    """,
                    (os_id,),
                )
                print('OS', os_id, cur.fetchone())
            cur.execute("SELECT id, razon_social FROM customers WHERE UPPER(razon_social) IN (UPPER('MIGRACION'), UPPER('MGBIO'), UPPER('SICOMED'), UPPER('CLINICA CRUZ CELESTE')) ORDER BY id")
            print('Customers present:', cur.fetchall())

if __name__ == '__main__':
    main()
