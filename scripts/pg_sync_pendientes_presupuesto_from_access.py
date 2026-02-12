"""
Sync "pendientes de presupuesto" from Microsoft Access into Postgres for a given list of OS Ids.

What it does (per OS Id):
- Ensure customer exists by CodEmpresa/NombreEmpresa (may create customer)
- Map brand/model only to existing PG records (never create new brands/models)
- Find or create device by NumeroSerie + customer; only fills marca/model if IDs exist
- Upsert ingreso:
  * presupuesto_estado -> 'pendiente' unless already emitido/enviado/presupuestado/aprobado/rechazado
  * fecha_servicio -> set from Access if missing in PG
  * fecha_ingreso -> use Access if present (keeps PG if Access missing)
  * ubicacion -> set to 'Taller' if it exists
  * estado -> if current is 'entregado' and env SET_ENTREGADO_TO is set, change to that value

Usage:
  POSTGRES_* env vars for connection. Optional env SET_ENTREGADO_TO.
  python scripts/pg_sync_pendientes_presupuesto_from_access.py --ids-file etl/pendientes_os_ids.txt
  python scripts/pg_sync_pendientes_presupuesto_from_access.py --dry-run --ids 25221 25222
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import psycopg  # type: ignore
import pyodbc    # type: ignore
from scripts.brand_canonical_data import CANONICAL_BRANDS


ACCESS_DB = r"Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb"


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def connect_pg():
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    return psycopg.connect(dsn)


def connect_access():
    conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};Dbq={ACCESS_DB};"
    return pyodbc.connect(conn_str, autocommit=True)


@dataclass
class AccessRow:
    id: int
    cod_empresa: str
    equipo: Optional[str]
    fecha_ingreso: Optional[str]
    marca: Optional[str]
    numero_serie: Optional[str]
    nombre_empresa: Optional[str]
    modelo: Optional[str]
    propietario: Optional[str]
    fecha_serv: Optional[str]


def fetch_access_rows(ids: Sequence[int]) -> List[AccessRow]:
    if not ids:
        return []
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
        out: List[AccessRow] = []
        for row in cur.fetchall():
            out.append(
                AccessRow(
                    id=int(row[0]),
                    cod_empresa=(row[1] or "").strip(),
                    equipo=(row[2] or None),
                    fecha_ingreso=row[3].isoformat() if row[3] else None,
                    marca=(row[4] or None),
                    numero_serie=(row[5] or None),
                    nombre_empresa=(row[6] or None),
                    modelo=(row[7] or None),
                    propietario=(row[8] or None),
                    fecha_serv=row[9].isoformat() if row[9] else None,
                )
            )
        return out
    finally:
        try:
            cn.close()
        except Exception:
            pass


def get_or_create_customer(cur, cod_empresa: Optional[str], nombre: Optional[str]) -> Optional[int]:
    cod = (cod_empresa or "").strip()
    nom = (nombre or "").strip()
    if cod:
        cur.execute("SELECT id FROM customers WHERE UPPER(TRIM(cod_empresa))=UPPER(TRIM(%s)) LIMIT 1", (cod,))
        r = cur.fetchone()
        if r:
            return int(r[0])
    if nom:
        cur.execute("SELECT id FROM customers WHERE UPPER(TRIM(razon_social))=UPPER(TRIM(%s)) LIMIT 1", (nom,))
        r = cur.fetchone()
        if r:
            if cod:
                cur.execute("UPDATE customers SET cod_empresa=%s WHERE id=%s AND (cod_empresa IS NULL OR TRIM(cod_empresa)='')", (cod, int(r[0])))
            return int(r[0])
    if not nom and not cod:
        return None
    cur.execute(
        "INSERT INTO customers(razon_social, cod_empresa) VALUES (%s,%s) RETURNING id",
        (nom or cod or "(sin nombre)", cod or None),
    )
    return int(cur.fetchone()[0])


def _norm_key(s: str) -> str:
    return "".join(ch for ch in s.upper().strip() if ch.isalnum())


def load_pg_brand_index(cur) -> Dict[str, int]:
    cur.execute("SELECT id, nombre FROM marcas")
    idx: Dict[str, int] = {}
    for (bid, nombre) in cur.fetchall():
        if not nombre:
            continue
        idx[_norm_key(str(nombre))] = int(bid)
    return idx


def load_pg_model_index(cur) -> Dict[Tuple[int, str], List[Tuple[int, Optional[str]]]]:
    cur.execute("SELECT id, marca_id, nombre, tipo_equipo FROM models")
    idx: Dict[Tuple[int, str], List[Tuple[int, Optional[str]]]] = {}
    for (mid, marca_id, nombre, tipo_equipo) in cur.fetchall():
        key = (int(marca_id), _norm_key(str(nombre or "")))
        idx.setdefault(key, []).append((int(mid), (tipo_equipo or None)))
    return idx


def build_brand_alias_index() -> Dict[str, str]:
    alias_to_canon: Dict[str, str] = {}
    for canon, meta in CANONICAL_BRANDS.items():
        alias_to_canon[_norm_key(canon)] = canon
        for a in meta.get("aliases", []) or []:
            alias_to_canon[_norm_key(a)] = canon
    return alias_to_canon


def find_brand_id(brand_idx: Dict[str, int], alias_idx: Dict[str, str], nombre: Optional[str]) -> Optional[int]:
    n = (nombre or "").strip()
    if not n:
        return None
    k = _norm_key(n)
    if k in brand_idx:
        return brand_idx[k]
    canon = alias_idx.get(k)
    if canon:
        kc = _norm_key(canon)
        if kc in brand_idx:
            return brand_idx[kc]
    return None


def find_model_id(model_idx: Dict[Tuple[int, str], List[Tuple[int, Optional[str]]]], marca_id: Optional[int], nombre: Optional[str]) -> Optional[int]:
    if not marca_id:
        return None
    n = (nombre or "").strip()
    if not n:
        return None
    key = (int(marca_id), _norm_key(n))
    cands = model_idx.get(key)
    if not cands:
        return None
    cands_sorted = sorted(cands, key=lambda t: (t[1] is None, t[0]))
    return cands_sorted[0][0]


def find_or_create_device(cur, customer_id: Optional[int], marca_id: Optional[int], model_id: Optional[int], numero_serie: Optional[str], propietario: Optional[str]) -> Optional[int]:
    ns = (numero_serie or "").strip()
    if ns:
        if customer_id:
            cur.execute(
                "SELECT id FROM devices WHERE customer_id=%s AND UPPER(TRIM(numero_serie))=UPPER(TRIM(%s)) ORDER BY id LIMIT 1",
                (customer_id, ns),
            )
            r = cur.fetchone()
            if r:
                if marca_id or model_id:
                    cur.execute(
                        "UPDATE devices SET marca_id=COALESCE(marca_id,%s), model_id=COALESCE(model_id,%s) WHERE id=%s",
                        (marca_id, model_id, int(r[0])),
                    )
                return int(r[0])
        cur.execute(
            "SELECT id FROM devices WHERE UPPER(TRIM(numero_serie))=UPPER(TRIM(%s)) ORDER BY id LIMIT 1",
            (ns,),
        )
        r = cur.fetchone()
        if r:
            cur.execute(
                "UPDATE devices SET customer_id=COALESCE(customer_id,%s), marca_id=COALESCE(marca_id,%s), model_id=COALESCE(model_id,%s) WHERE id=%s",
                (customer_id, marca_id, model_id, int(r[0])),
            )
            return int(r[0])
    if not customer_id:
        return None
    cur.execute(
        "INSERT INTO devices(customer_id, marca_id, model_id, numero_serie, propietario) VALUES (%s,%s,%s, NULLIF(%s,''), NULLIF(%s,'')) RETURNING id",
        (customer_id, (marca_id or None), (model_id or None), ns or None, (propietario or None)),
    )
    return int(cur.fetchone()[0])


def upsert_ingreso(cur, ingreso_id: int, device_id: int, fecha_ingreso: Optional[str], fecha_serv: Optional[str], loc_taller_id: Optional[int], fix_ubic: bool, set_entregado_to: Optional[str], dry_run: bool = False) -> Tuple[str, Optional[str]]:
    cur.execute("SELECT id, presupuesto_estado, fecha_ingreso, fecha_servicio, ubicacion_id, estado FROM ingresos WHERE id=%s", (ingreso_id,))
    r = cur.fetchone()
    if not r:
        if dry_run:
            return ("create", None)
        cur.execute(
            """
            INSERT INTO ingresos(id, device_id, estado, motivo, fecha_ingreso, fecha_creacion, fecha_servicio, presupuesto_estado)
            VALUES (%s, %s, 'ingresado', 'reparacion', %s, COALESCE(%s, NOW()), %s, 'pendiente')
            RETURNING id
            """,
            (ingreso_id, device_id, fecha_ingreso, fecha_ingreso, fecha_serv),
        )
        if fix_ubic and loc_taller_id:
            cur.execute("UPDATE ingresos SET ubicacion_id=%s WHERE id=%s", (loc_taller_id, ingreso_id))
        return ("created", None)
    presu = (r[1] or "").strip().lower()
    if presu not in ("aprobado", "rechazado", "presupuestado", "emitido", "enviado"):
        if not dry_run:
            cur.execute("UPDATE ingresos SET presupuesto_estado='pendiente' WHERE id=%s", (ingreso_id,))
    if (r[3] is None) and fecha_serv and not dry_run:
        cur.execute("UPDATE ingresos SET fecha_servicio=%s WHERE id=%s", (fecha_serv, ingreso_id))
    if fecha_ingreso and not dry_run:
        cur.execute("UPDATE ingresos SET fecha_ingreso=%s WHERE id=%s", (fecha_ingreso, ingreso_id))
    if fix_ubic and loc_taller_id and (r[4] != loc_taller_id) and not dry_run:
        cur.execute("UPDATE ingresos SET ubicacion_id=%s WHERE id=%s", (loc_taller_id, ingreso_id))
    est = (r[5] or '').strip().lower()
    if est == 'entregado' and set_entregado_to and not dry_run:
        cur.execute("UPDATE ingresos SET estado=%s WHERE id=%s", (set_entregado_to, ingreso_id))
    return ("updated", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*", type=int, help="OS Ids to sync")
    ap.add_argument("--ids-file", type=str, help="File with one OS Id per line")
    ap.add_argument("--dry-run", action="store_true", help="Do not commit changes")
    args = ap.parse_args()

    ids: List[int] = []
    if args.ids:
        ids.extend(args.ids)
    if args.ids_file:
        with open(args.ids_file, "r", encoding="utf-8") as f:
            for line in f:
                s = (line or "").strip()
                if not s:
                    continue
                try:
                    ids.append(int(s))
                except Exception:
                    pass
    ids = sorted(set(ids))
    if not ids:
        print("No OS Ids provided (--ids or --ids-file)")
        return

    acc_rows = fetch_access_rows(ids)
    found_ids = {r.id for r in acc_rows}
    missing = [i for i in ids if i not in found_ids]
    if missing:
        print("WARN: Not found in Access:", missing)

    cn = connect_pg()
    try:
        with cn.transaction():
            with cn.cursor() as cur:
                brand_idx = load_pg_brand_index(cur)
                model_idx = load_pg_model_index(cur)
                alias_idx = build_brand_alias_index()
                cur.execute("SELECT id FROM locations WHERE LOWER(nombre)=LOWER(%s) LIMIT 1", ("taller",))
                loc_row = cur.fetchone()
                loc_taller_id = int(loc_row[0]) if loc_row else None
                for r in acc_rows:
                    cust_id = get_or_create_customer(cur, r.cod_empresa, r.nombre_empresa)
                    marca_id = find_brand_id(brand_idx, alias_idx, r.marca)
                    model_id = find_model_id(model_idx, marca_id, r.modelo)
                    dev_id = find_or_create_device(cur, cust_id, marca_id, model_id, r.numero_serie, r.propietario)
                    if not dev_id:
                        print(f"[OS {r.id}] ERROR: cannot determine/create device (customer={cust_id} ns={r.numero_serie!r})")
                        continue
                    action, presu_action = upsert_ingreso(
                        cur,
                        r.id,
                        dev_id,
                        r.fecha_ingreso,
                        r.fecha_serv,
                        loc_taller_id,
                        fix_ubic=True,
                        set_entregado_to=os.getenv('SET_ENTREGADO_TO') or None,
                        dry_run=args.dry_run,
                    )
                    print(f"[OS {r.id}] {action} | cliente={cust_id} device={dev_id} marca={marca_id} modelo={model_id}")
        if args.dry_run:
            cn.rollback()
            print("DRY RUN: changes discarded")
        else:
            cn.commit()
            print("Changes committed")
    finally:
        try:
            cn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

