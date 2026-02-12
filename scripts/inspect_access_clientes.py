import pyodbc

DB_PATH = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"

def main():
    cn = pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={DB_PATH};", autocommit=True)
    cur = cn.cursor()
    cur.execute("SELECT * FROM [Clientes] WHERE 1=0")
    cols = [c[0] for c in cur.description]
    print('Clientes cols:', cols)
    cur.execute("SELECT TOP 10 * FROM [Clientes]")
    rows = cur.fetchall()
    for r in rows:
        print([r[i] for i in range(len(cols))])
    cn.close()

if __name__ == '__main__':
    main()

