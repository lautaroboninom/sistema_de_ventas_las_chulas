import pymysql

conn = pymysql.connect(host='127.0.0.1', port=3306, user='sepid', password='supersegura', database='servicio_tecnico', charset='utf8mb4')
with conn.cursor() as cur:
    cur.execute("SELECT id, nombre, activo FROM catalogo_accesorios ORDER BY id")
    rows = cur.fetchall()
    print('CATALOGO', len(rows))
    for r in rows:
        print(r)
    cur.execute("""
        SELECT DISTINCT ca.id, ca.nombre
        FROM ingreso_accesorios ia JOIN catalogo_accesorios ca ON ca.id=ia.accesorio_id
        ORDER BY ca.id
    """)
    used = cur.fetchall()
    print('\nUSADOS', len(used))
    for r in used:
        print(r)
conn.close()

