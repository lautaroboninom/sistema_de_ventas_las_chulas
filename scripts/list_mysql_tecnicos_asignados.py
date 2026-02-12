import pymysql

def main():
    conn = pymysql.connect(host='127.0.0.1', port=3306, user='sepid', password='supersegura', database='servicio_tecnico', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT u.id, COALESCE(u.nombre,'' ) AS nombre, COALESCE(u.email,'') AS email
            FROM ingresos i JOIN users u ON u.id = i.asignado_a
            WHERE i.asignado_a IS NOT NULL
            ORDER BY u.id
        """)
        rows = cur.fetchall()
        print('MYSQL_tecnicos_asignados:', len(rows))
        for r in rows:
            print(r['id'], r['nombre'], r['email'])
    conn.close()

if __name__ == '__main__':
    main()

