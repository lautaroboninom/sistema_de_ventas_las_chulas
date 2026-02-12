import pymysql

def main():
    conn = pymysql.connect(host='127.0.0.1', port=3306, user='sepid', password='supersegura', database='servicio_tecnico', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT VERSION() AS v')
            print('VERSION', cur.fetchone()['v'])
            for t in ['ingresos','devices','customers','locations']:
                try:
                    cur.execute(f'SELECT COUNT(*) AS c FROM {t}')
                    print(t.upper(), cur.fetchone()['c'])
                except Exception as e:
                    print(t.upper()+'_ERR', e)
    finally:
        conn.close()

if __name__ == '__main__':
    main()

