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
    os_id = int(os.getenv('OS_ID', '15177'))
    with connect_pg() as cn:
        with cn.cursor() as cur:
            cur.execute("SELECT id FROM customers WHERE UPPER(razon_social)=UPPER('MGBIO')")
            mgbio = int(cur.fetchone()[0])
            cur.execute("SELECT device_id FROM ingresos WHERE id=%s", (os_id,))
            dev = int(cur.fetchone()[0])
            cur.execute("UPDATE devices SET customer_id=%s WHERE id=%s", (mgbio, dev))
        cn.commit()
    with connect_pg() as cn:
        with cn.cursor() as cur:
            cur.execute("""
                SELECT i.id, c.razon_social FROM ingresos i
                JOIN devices d ON d.id=i.device_id
                JOIN customers c ON c.id=d.customer_id
                WHERE i.id=%s
            """, (os_id,))
            print(cur.fetchone())

if __name__ == '__main__':
    main()

