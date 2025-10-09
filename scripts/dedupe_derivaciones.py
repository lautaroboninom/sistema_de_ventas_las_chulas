import os
import psycopg


def env(name, default=None):
    return os.getenv(name, default)


def connect():
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    return psycopg.connect(dsn)


def dedupe(conn, apply=False):
    """Remove duplicate equipos_derivados rows keeping the lowest id.

    Duplicates are defined for open derivaciones (estado='derivado' AND fecha_entrega IS NULL)
    sharing the same: ingreso_id, proveedor_id, remit_deriv (trim), fecha_deriv, comentarios (trim).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH base AS (
              SELECT
                id,
                ingreso_id,
                proveedor_id,
                COALESCE(TRIM(remit_deriv),'') AS remit_key,
                fecha_deriv,
                COALESCE(TRIM(comentarios),'') AS coment_key,
                ROW_NUMBER() OVER (
                  PARTITION BY ingreso_id, proveedor_id, COALESCE(TRIM(remit_deriv),''), fecha_deriv, COALESCE(TRIM(comentarios),'')
                  ORDER BY id ASC
                ) AS rn
              FROM equipos_derivados
              WHERE estado = 'derivado' AND fecha_entrega IS NULL
            )
            SELECT id FROM base WHERE rn > 1
            """
        )
        dup_ids = [r[0] for r in cur.fetchall()]

    if not dup_ids:
        print('No duplicates found.')
        return 0

    print(f'Found {len(dup_ids)} duplicate rows to delete: {dup_ids[:10]}{"..." if len(dup_ids)>10 else ""}')
    if not apply:
        print('Dry-run (no changes applied). Run with APPLY=1 to delete.')
        return 0

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM equipos_derivados WHERE id = ANY(%s)", (dup_ids,))
            print('Deleted:', cur.rowcount)
            return cur.rowcount or 0


def main():
    apply = (env('APPLY','0') in ('1','true','TRUE','yes','y'))
    conn = connect()
    try:
        dedupe(conn, apply=apply)
    finally:
        conn.close()


if __name__ == '__main__':
    main()

