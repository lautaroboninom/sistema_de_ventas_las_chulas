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
            cur.execute("SELECT COUNT(*) FROM models")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM models WHERE tipo_equipo IS NULL OR LENGTH(TRIM(tipo_equipo))=0")
            missing = cur.fetchone()[0]
            print('models_total', total)
            print('models_missing_tipo', missing)

if __name__ == '__main__':
    main()

