from django.core.management.base import BaseCommand
from django.db import connection, transaction
import csv
import subprocess
import shlex
import os
from datetime import datetime
from typing import Dict, Any, Optional


def _norm_code(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    s = str(code).strip().upper()
    import re
    m = re.match(r"^(MG|NM|NV|CE)[^0-9]*(\d{1,6})$", s)
    if not m:
        return None
    pref, num = m.group(1), m.group(2)
    return f"{pref} {num[-4:].zfill(4)}"


def _ns_key(ns: Optional[str]) -> str:
    return (ns or "").strip().upper().replace(" ", "").replace("-", "")


class Command(BaseCommand):
    help = "Cruza Access (Servicio) 2024 con ingresos 2024; marca entregados/alquilados y completa NS si faltan."

    def add_arguments(self, parser):
        parser.add_argument(
            "--accdb",
            default=r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb",
            help="Ruta del .accdb (Access)",
        )
        parser.add_argument("--apply", action="store_true", help="Aplica cambios (por defecto dry-run)")
        parser.add_argument(
            "--out",
            default="docs/sync_from_access_2024.csv",
            help="CSV de salida con el detalle",
        )

    def _export_access_csv(self, accdb_path: str, out_csv: str) -> None:
        ps = "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.Data; " \
             + "$p='%s'; $con=New-Object System.Data.OleDb.OleDbConnection (\"Provider=Microsoft.ACE.OLEDB.12.0;Data Source=$p;Persist Security Info=False;\"); " % accdb_path \
             + "try{$con.Open()}catch{$con=New-Object System.Data.OleDb.OleDbConnection (\"Provider=Microsoft.ACE.OLEDB.16.0;Data Source=$p;Persist Security Info=False;\"); $con.Open()}; " \
             + "$cmd=$con.CreateCommand(); $cmd.CommandText='SELECT Id, [Fecha Ingreso] AS FechaIngreso, NdeControl, NumeroSerie, Entregado, Alquilado, [FechaEntrega], Marca, Modelo FROM Servicio WHERE Year([Fecha Ingreso])=2024 OR Year([FechaEntrega])=2024'; " \
             + "$da=New-Object System.Data.OleDb.OleDbDataAdapter $cmd; $dt=New-Object System.Data.DataTable; [void]$da.Fill($dt); " \
             + "$csvPath='%s'; $sw=New-Object System.IO.StreamWriter($csvPath, $false, [System.Text.Encoding]::UTF8); " % out_csv \
             + "$cols=$dt.Columns | ForEach-Object {$_.ColumnName}; $sw.WriteLine(($cols -join ',')); " \
             + "foreach ($row in $dt.Rows){ $values=@(); foreach($c in $cols){ $v=$row[$c]; if ($v -is [DateTime]){ $values+=$v.ToString('s') } else { $s= [string]$v; $s=$s -replace '\"',''''; $values+=$s } }; $sw.WriteLine(($values -join ',')) }; $sw.Close(); $con.Close();"
        # Run PowerShell to produce CSV
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=False)

    def handle(self, *args, **opts):
        accdb = opts.get("accdb")
        out_csv = opts.get("out")
        apply = bool(opts.get("apply"))

        tmp_csv = out_csv  # reuse path for export, will append results later
        self._export_access_csv(accdb, tmp_csv)

        # Load Access rows into maps
        by_code: Dict[str, Dict[str, Any]] = {}
        by_ns: Dict[str, Dict[str, Any]] = {}
        with open(tmp_csv, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    code = _norm_code(row.get("NdeControl"))
                    nskey = _ns_key(row.get("NumeroSerie"))
                    # pick best row preferring Entregado then Alquilado, else latest FechaIngreso
                    def better(a: Optional[Dict[str, Any]], b: Dict[str, Any]) -> Dict[str, Any]:
                        if a is None:
                            return b
                        a_ent = str(a.get("Entregado", "")).strip().lower() in ("true","1","-1")
                        b_ent = str(b.get("Entregado", "")).strip().lower() in ("true","1","-1")
                        if a_ent != b_ent:
                            return b if b_ent else a
                        a_alq = str(a.get("Alquilado", "")).strip().lower() in ("true","1","-1")
                        b_alq = str(b.get("Alquilado", "")).strip().lower() in ("true","1","-1")
                        if a_alq != b_alq:
                            return b if b_alq else a
                        def parse_dt(s):
                            try:
                                return datetime.fromisoformat(str(s))
                            except Exception:
                                return datetime.min
                        if parse_dt(b.get("FechaIngreso")) > parse_dt(a.get("FechaIngreso")):
                            return b
                        return a
                    if code:
                        by_code[code] = better(by_code.get(code), row)
                    if nskey:
                        by_ns[nskey] = better(by_ns.get(nskey), row)
                except Exception:
                    continue

        # Query our ingresos 2024 pending
        with connection.cursor() as cur:
            # Asegurar ubicación placeholder "-"
            cur.execute("INSERT INTO locations(nombre) VALUES ('-') ON CONFLICT DO NOTHING")
            dash_id = None
            try:
                cur.execute("SELECT id FROM locations WHERE nombre='-' LIMIT 1")
                r_dash = cur.fetchone()
                dash_id = int(r_dash[0]) if r_dash else None
            except Exception:
                dash_id = None
            cur.execute(
                """
                SELECT t.id, t.estado, t.fecha_ingreso, t.fecha_entrega,
                       d.id AS device_id, COALESCE(d.numero_interno,''), COALESCE(d.n_de_control,''), COALESCE(d.numero_serie,'')
                  FROM ingresos t
                  JOIN devices d ON d.id = t.device_id
                 WHERE DATE(t.fecha_ingreso) >= DATE '2024-01-01' AND DATE(t.fecha_ingreso) <= DATE '2024-12-31'
                   AND t.estado NOT IN ('entregado','alquilado','baja')
                """
            )
            rows = cur.fetchall() or []

        updates = []  # (ingreso_id, set_entregado:bool, fecha_entrega:datetime|None, set_alquilado:bool, new_ns:str|None)
        for ingreso_id, estado, f_ing, f_ent, device_id, numint, ndc, ns in rows:
            code = _norm_code(numint or ndc)
            nskey = _ns_key(ns)
            acc = None
            if code and code in by_code:
                acc = by_code.get(code)
            elif nskey and nskey in by_ns:
                acc = by_ns.get(nskey)
            if not acc:
                continue
            acc_ent = str(acc.get("Entregado", "")).strip().lower() in ("true","1","-1")
            acc_alq = str(acc.get("Alquilado", "")).strip().lower() in ("true","1","-1")
            acc_fent = acc.get("FechaEntrega") or ""
            try:
                acc_fent_dt = datetime.fromisoformat(str(acc_fent)) if acc_fent else None
            except Exception:
                acc_fent_dt = None
            acc_ns = (acc.get("NumeroSerie") or "").strip()
            new_ns = None
            if not nskey and acc_ns:
                new_ns = acc_ns
            updates.append((int(ingreso_id), bool(acc_ent), acc_fent_dt, bool(acc_alq), new_ns))

        # Apply
        if apply and updates:
            with transaction.atomic():
                with connection.cursor() as cur:
                    for ingreso_id, set_ent, f_ent_dt, set_alq, new_ns in updates:
                        if set_ent:
                            cur.execute(
                                "UPDATE ingresos SET estado='entregado', fecha_entrega=COALESCE(fecha_entrega, %s), ubicacion_id = COALESCE(%s, ubicacion_id) WHERE id=%s",
                                [
                                    f_ent_dt.date().isoformat() if (f_ent_dt and hasattr(f_ent_dt, 'date')) else None,
                                    dash_id,
                                    ingreso_id,
                                ],
                            )
                        elif set_alq:
                            cur.execute(
                                "UPDATE ingresos SET estado='alquilado', alquilado=true, ubicacion_id = COALESCE(%s, ubicacion_id) WHERE id=%s",
                                [dash_id, ingreso_id],
                            )
                        if new_ns:
                            cur.execute(
                                "UPDATE devices SET numero_serie=%s WHERE id=(SELECT device_id FROM ingresos WHERE id=%s) AND (numero_serie IS NULL OR TRIM(numero_serie)='')",
                                [new_ns, ingreso_id],
                            )

        # Write result CSV
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        with open(out_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ingreso_id", "set_entregado", "fecha_entrega", "set_alquilado", "new_numero_serie"])
            for row in updates:
                ingreso_id, set_ent, f_ent_dt, set_alq, new_ns = row
                w.writerow([ingreso_id, int(set_ent), (f_ent_dt.isoformat() if f_ent_dt else ""), int(set_alq), new_ns or ""])

        self.stdout.write(
            f"OK {'(APLICADO)' if apply else '(dry-run)'}: matched={len(updates)} | CSV: {out_csv}"
        )
