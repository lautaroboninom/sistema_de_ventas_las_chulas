import pymysql

def main():
    conn = pymysql.connect(host='127.0.0.1', port=3306, user='sepid', password='supersegura', database='servicio_tecnico', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS c FROM ingresos WHERE asignado_a IS NOT NULL')
        nn = int(cur.fetchone()['c'])
        cur.execute('SELECT COUNT(*) AS c FROM ingresos')
        tt = int(cur.fetchone()['c'])
        print('MYSQL_asignado_no_null', nn)
        print('MYSQL_total', tt)
    conn.close()

if __name__ == '__main__':
    main()

