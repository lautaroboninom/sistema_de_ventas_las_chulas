import pymysql

def main():
    conn = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="sepid",
        password="supersegura",
        database="servicio_tecnico",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            print("DESCRIBE ingresos:")
            cur.execute("DESCRIBE ingresos")
            for row in cur.fetchall():
                print(f"- {row['Field']}: {row['Type']} NULL={row['Null']} KEY={row['Key']} DEFAULT={row['Default']}")
        print("\nUltimos 10 ingresos:")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, device_id, ubicacion_id, motivo, fecha_ingreso, remito_ingreso, remito_salida, factura_numero, asignado_a, recibido_por FROM ingresos ORDER BY id DESC LIMIT 10"
            )
            for r in cur.fetchall():
                print(r)
        print("\nUbicaciones en MySQL:")
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre FROM locations ORDER BY id")
            for r in cur.fetchall():
                print(r)
        print("\nClientes ejemplo de devices:")
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id as device_id, d.customer_id, c.razon_social as customer_nombre
                FROM devices d
                LEFT JOIN customers c ON c.id=d.customer_id
                ORDER BY d.id DESC LIMIT 10
                """
            )
            for r in cur.fetchall():
                print(r)
    finally:
        conn.close()

if __name__ == "__main__":
    main()

