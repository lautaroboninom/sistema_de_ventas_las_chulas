import os
import sys
import psycopg


def env(name, default=None):
    return os.getenv(name, default)


def connect():
    host = env('POSTGRES_HOST', '127.0.0.1')
    port = env('POSTGRES_PORT', '5433')  # compose expone 5433:5432
    db   = env('POSTGRES_DB', 'servicio_tecnico-dev')
    user = env('POSTGRES_USER', 'sepid')
    pw   = env('POSTGRES_PASSWORD', '')
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)


def main():
    if len(sys.argv) < 2:
        print('Uso: python scripts/delete_derivaciones_for_ingreso.py <ingreso_id>')
        sys.exit(1)
    ingreso_id = int(sys.argv[1])
    conn = connect()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, proveedor_id, remit_deriv, fecha_deriv, fecha_entrega, estado FROM equipos_derivados WHERE ingreso_id=%s ORDER BY id",
                    (ingreso_id,),
                )
                rows = cur.fetchall()
                print('Antes:', rows)
                cur.execute("DELETE FROM equipos_derivados WHERE ingreso_id=%s", (ingreso_id,))
                print('Eliminadas:', cur.rowcount)
                cur.execute("UPDATE ingresos SET estado='ingresado' WHERE id=%s AND estado='derivado'", (ingreso_id,))
                print('Ingreso actualizado a ingresado (si correspondia).')
    finally:
        conn.close()


if __name__ == '__main__':
    main()

