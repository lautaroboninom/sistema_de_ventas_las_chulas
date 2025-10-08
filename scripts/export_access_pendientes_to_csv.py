import csv
from pathlib import Path
import pyodbc  # type: ignore

ACCESS_DB = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"
OUT = Path('etl/out/pendientes_presupuesto_access.csv')
IDS_FILE = Path('etl/pendientes_os_ids.txt')


def connect_access():
    cn = pyodbc.connect(f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={ACCESS_DB};", autocommit=True)
    return cn


def load_ids():
    ids = []
    with IDS_FILE.open('r', encoding='utf-8') as f:
        for line in f:
            s = (line or '').strip()
            if not s:
                continue
            try:
                ids.append(int(s))
            except Exception:
                pass
    return ids


def main():
    ids = load_ids()
    if not ids:
        print('Sin IDs en', IDS_FILE)
        return
    cn = connect_access()
    try:
        cur = cn.cursor()
        id_list = ",".join(str(int(i)) for i in ids)
        sql = f"""
            SELECT s.Id,
                   s.CodEmpresa,
                   eq.Equipo,
                   s.[Fecha Ingreso] AS FechaIngreso,
                   s.Marca,
                   s.NumeroSerie,
                   c.[NombreEmpresa],
                   s.Modelo,
                   s.Propietario,
                   rs.FechaServ
            FROM (([Servicio] AS s
            LEFT JOIN [Clientes] AS c ON (UCase(Trim(c.CodEmpresa)) = UCase(Trim(s.CodEmpresa))))
            LEFT JOIN [Equipos] AS eq ON (eq.IdEquipos = s.IdEquipo))
            LEFT JOIN [RegistrosdeServicio] AS rs ON (rs.Id = s.Id)
            WHERE s.Id IN ({id_list})
            ORDER BY s.Id
        """
        cur.execute(sql)
        rows = cur.fetchall()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open('w', encoding='utf-8', newline='') as f:
            cw = csv.writer(f)
            cw.writerow(['Id','CodEmpresa','Equipo','FechaIngreso','Marca','NumeroSerie','NombreEmpresa','Modelo','Propietario','FechaServ'])
            for r in rows:
                cw.writerow([
                    r[0], r[1], r[2], r[3].strftime('%Y-%m-%d') if r[3] else '', r[4], r[5], r[6], r[7], r[8], r[9].strftime('%Y-%m-%d') if r[9] else ''
                ])
        print('Exportado a', OUT)
    finally:
        try:
            cn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

