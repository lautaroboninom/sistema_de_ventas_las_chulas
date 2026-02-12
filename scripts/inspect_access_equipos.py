import pyodbc

DB_PATH = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"

def main():
    cn = pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={DB_PATH};", autocommit=True)
    cur = cn.cursor()
    try:
        cur.execute("SELECT * FROM [Equipos] WHERE 1=0")
    except Exception as e:
        print('Equipos open error:', e)
        return
    cols = [c[0] for c in cur.description]
    print('Equipos cols:', cols)
    cur.execute("SELECT TOP 10 * FROM [Equipos]")
    rows = cur.fetchall()
    for r in rows:
        print([r[i] for i in range(len(cols))])
    cn.close()

if __name__ == '__main__':
    main()

