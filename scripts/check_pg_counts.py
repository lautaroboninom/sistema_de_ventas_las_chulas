import os
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

tables = [
    'customers','marcas','models','catalogo_tipos_equipo','marca_tipos_equipo','marca_series','marca_series_variantes','model_hierarchy','proveedores_externos'
]

def main():
    with connect_pg() as conn:
        with conn.cursor() as cur:
            for t in tables:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {t}")
                    c = cur.fetchone()[0]
                except Exception as e:
                    c = f'ERR: {e}'
                print(f"{t}: {c}")

if __name__ == '__main__':
    main()

