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
    with connect_pg() as cn:
        with cn.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, d.id, COALESCE(d.numero_serie,''), COALESCE(b.nombre,''), COALESCE(m.nombre,'')
                FROM ingresos i
                JOIN devices d ON d.id=i.device_id
                JOIN customers c ON c.id=d.customer_id
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models m ON m.id=d.model_id
                WHERE UPPER(TRIM(c.razon_social)) LIKE 'MIGRACION%'
                ORDER BY i.id ASC
                LIMIT 50
                """
            )
            for r in cur.fetchall():
                print(r)

if __name__ == '__main__':
    main()

