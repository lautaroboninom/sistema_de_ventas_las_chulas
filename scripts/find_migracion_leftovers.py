import os
import psycopg  # type: ignore
try:
    import pyodbc  # type: ignore
except Exception:
    pyodbc = None

ACCESS_DB = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"

def connect_pg():
    host = os.getenv('PG_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
    port = int(os.getenv('PG_PORT', os.getenv('POSTGRES_PORT', '5433')))
    db = os.getenv('PG_DB', os.getenv('POSTGRES_DB', 'servicio_tecnico'))
    user = os.getenv('PG_USER', os.getenv('POSTGRES_USER', 'sepid'))
    pw = os.getenv('PG_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))
    dsn = f"host={host} port={port} dbname={db} user={user} password={pw}"
    return psycopg.connect(dsn)

def connect_access():
    assert pyodbc is not None
    return pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={ACCESS_DB};", autocommit=True)

def main():
    with connect_pg() as cn:
        with cn.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.device_id
                FROM ingresos i
                JOIN devices d ON d.id=i.device_id
                JOIN customers c ON c.id=d.customer_id
                WHERE UPPER(TRIM(c.razon_social)) LIKE 'MIGRACION%'
                ORDER BY i.id ASC
                LIMIT 100
                """
            )
            rows = cur.fetchall()
    if not rows:
        print('No quedan MIGRACION')
        return
    print('Quedan MIGRACION (sample 100):', len(rows))
    if pyodbc is None:
        for r in rows[:10]:
            print(r)
        return
    cn = connect_access()
    cur = cn.cursor()
    for (os_id, device_id) in rows[:30]:
        cur.execute("SELECT CodEmpresa FROM [Servicio] WHERE Id=?", (int(os_id),))
        a = cur.fetchone()
        cod = (a[0] or '').strip() if a else None
        nom = None
        if cod:
            cur.execute("SELECT NombreEmpresa FROM [Clientes] WHERE CodEmpresa=?", (cod,))
            b = cur.fetchone()
            nom = (b[0] or '').strip() if b else None
        print({'os': os_id, 'dev': device_id, 'cod': cod, 'name': nom})
    cn.close()

if __name__ == '__main__':
    main()

