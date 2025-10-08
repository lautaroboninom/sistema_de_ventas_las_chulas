import os
import sys
import psycopg

def env(name, default=None):
    return os.getenv(name, default)

def connect_pg():
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    return psycopg.connect(dsn)

def main():
    sql = sys.argv[1] if len(sys.argv) > 1 else "SELECT 1"
    with connect_pg() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            try:
                rows = cur.fetchall()
            except Exception:
                rows = []
            print("OK")
            for r in rows:
                print("| ", *r)

if __name__ == '__main__':
    main()

