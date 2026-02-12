import csv
import os
import psycopg
from pathlib import Path

BASE = Path('etl/out/access_export')


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


def norm(v):
    if v is None:
        return None
    s = str(v).strip()
    return s


def is_missing(v):
    if v is None:
        return True
    s = str(v).strip()
    if not s:
        return True
    return s.lower() in ('sin informacion', 'sin información', 'n/a', 'na', '-')


def load_csv(path: Path):
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def sync_customers(conn):
    rows = load_csv(BASE / 'Clientes.csv')
    if not rows:
        return {'updated': 0}
    updated = 0
    with conn.transaction():
        with conn.cursor() as cur:
            for r in rows:
                cod = norm(r.get('CodEmpresa'))
                name = norm(r.get('NombreEmpresa'))
                if not name:
                    continue
                contacto = norm(r.get('Contacto'))
                tel1 = norm(r.get('Telefono 1'))
                tel2 = norm(r.get('Telefono 2'))
                email = norm(r.get('E-mail'))

                # try by cod_empresa first
                row = None
                if cod:
                    cur.execute('SELECT id, razon_social, cod_empresa, contacto, telefono, telefono_2, email FROM customers WHERE cod_empresa=%s', (cod,))
                    row = cur.fetchone()
                if not row:
                    cur.execute('SELECT id, razon_social, cod_empresa, contacto, telefono, telefono_2, email FROM customers WHERE UPPER(TRIM(razon_social))=UPPER(TRIM(%s))', (name,))
                    row = cur.fetchone()
                if not row:
                    # create if not exists
                    cur.execute(
                        'INSERT INTO customers(razon_social, cod_empresa, contacto, telefono, telefono_2, email) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id',
                        (name, cod, contacto, tel1, tel2, email),
                    )
                    updated += 1
                    continue
                cid, razon_social, cod_empresa, c_contacto, c_tel1, c_tel2, c_email = row
                sets = []
                vals = []
                if cod and cod_empresa != cod:
                    sets.append('cod_empresa=%s'); vals.append(cod)
                if is_missing(c_contacto) and contacto:
                    sets.append('contacto=%s'); vals.append(contacto)
                if is_missing(c_tel1) and tel1:
                    sets.append('telefono=%s'); vals.append(tel1)
                if is_missing(c_tel2) and tel2:
                    sets.append('telefono_2=%s'); vals.append(tel2)
                if is_missing(c_email) and email:
                    sets.append('email=%s'); vals.append(email)
                if sets:
                    vals.append(cid)
                    cur.execute(f"UPDATE customers SET {', '.join(sets)} WHERE id=%s", vals)
                    updated += 1
    return {'updated': updated}


def sync_proveedores(conn):
    rows = load_csv(BASE / 'Proveedores.csv')
    if not rows:
        return {'updated': 0}
    updated = 0
    with conn.transaction():
        with conn.cursor() as cur:
            for r in rows:
                name = norm(r.get('NombreEmpresa'))
                if not name:
                    continue
                cur.execute('SELECT id, nombre FROM proveedores_externos WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))', (name,))
                row = cur.fetchone()
                if not row:
                    cur.execute('INSERT INTO proveedores_externos(nombre) VALUES (%s) ON CONFLICT DO NOTHING', (name,))
                    updated += 1
    return {'updated': updated}


def main():
    conn = connect_pg()
    try:
        res_c = sync_customers(conn)
        res_p = sync_proveedores(conn)
        print('Customers updated/created:', res_c['updated'])
        print('Providers updated/created:', res_p['updated'])
    finally:
        conn.close()


if __name__ == '__main__':
    main()

