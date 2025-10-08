"""
Importa catálogos base (clientes, marcas, modelos, variantes, proveedores y tipos de equipo)
desde una base MySQL al esquema PostgreSQL de la app.

Requiere:
  pip install PyMySQL psycopg[binary]

Variables de entorno MySQL:
  MYSQL_HOST, MYSQL_PORT, MYSQL_DB, MYSQL_USER, MYSQL_PASSWORD

Variables de entorno PostgreSQL (o .env ya cargado por tu shell):
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

Uso:
  python etl/mysql_to_pg/import_catalogs_from_mysql.py

Notas:
  - El script es tolerante a diferencias de nombres de tablas/columnas en MySQL
    (e.g. clientes vs customers; modelos vs models; equipos vs tipos_equipo).
  - Si en MySQL los modelos guardan id de tipo_equipo (p.e. id_tipo_equipo), se resuelve
    a su nombre usando la tabla de equipos.
  - Construye catálogo jerárquico por marca->tipo->serie->variante a partir de los modelos.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pymysql  # type: ignore
import psycopg


# ------------- Helpers de conexión -------------

def env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def connect_mysql():
    conn = pymysql.connect(
        host=env("MYSQL_HOST", "127.0.0.1"),
        port=int(env("MYSQL_PORT", "3306") or 3306),
        user=env("MYSQL_USER", "root"),
        password=env("MYSQL_PASSWORD", ""),
        database=env("MYSQL_DB", "servicio_tecnico"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    return conn


def connect_pg():
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    return psycopg.connect(dsn)


# ------------- MySQL metadata / lecturas -------------

def mysql_table_exists(conn, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE %s", (name,))
        return cur.fetchone() is not None


def mysql_columns(conn, table: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(f"DESCRIBE `{table}`")
        return [row["Field"] for row in cur.fetchall()]


def pick_first_present(cols: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    s = {c.lower(): c for c in cols}
    for cand in candidates:
        key = cand.lower()
        if key in s:
            return s[key]
    return None


def fetch_customers(conn) -> List[Dict[str, Any]]:
    tables = ["customers", "clientes"]
    for t in tables:
        if mysql_table_exists(conn, t):
            cols = mysql_columns(conn, t)
            id_col = pick_first_present(cols, ["id", "Id", "IdCliente", "customer_id"])
            name_col = pick_first_present(cols, ["razon_social", "RazonSocial", "razon", "nombre", "name", "company"])
            if not name_col:
                continue
            with conn.cursor() as cur:
                sel = f"SELECT {id_col or 'NULL'} AS id, `{name_col}` AS razon_social FROM `{t}`"
                cur.execute(sel)
                rows = cur.fetchall()
                return rows
    return []


def fetch_marcas(conn) -> List[Dict[str, Any]]:
    tables = ["marcas", "brands"]
    for t in tables:
        if mysql_table_exists(conn, t):
            cols = mysql_columns(conn, t)
            id_col = pick_first_present(cols, ["id", "Id", "id_marca", "IdMarca", "brand_id"])
            name_col = pick_first_present(cols, ["nombre", "Nombre", "name", "brand"])
            if not name_col:
                continue
            with conn.cursor() as cur:
                sel = f"SELECT {id_col or 'NULL'} AS id, `{name_col}` AS nombre FROM `{t}`"
                cur.execute(sel)
                return cur.fetchall()
    return []


def fetch_equipos(conn) -> Tuple[List[Dict[str, Any]], Dict[Any, str]]:
    tables = ["equipos", "tipos_equipo", "tipo_equipo", "equipment_types"]
    for t in tables:
        if mysql_table_exists(conn, t):
            cols = mysql_columns(conn, t)
            id_col = pick_first_present(cols, ["IdEquipos", "id", "tipo_id", "Id", "codigo"])
            name_col = pick_first_present(cols, ["Equipo", "equipo", "nombre", "name"]) or "nombre"
            with conn.cursor() as cur:
                sel = f"SELECT {id_col or 'NULL'} AS id, `{name_col}` AS nombre FROM `{t}`"
                cur.execute(sel)
                rows = cur.fetchall()
                idx = {}
                for r in rows:
                    if r.get("id") is not None:
                        idx[r["id"]] = r.get("nombre")
                return rows, idx
    return [], {}


def fetch_models(conn, equipos_idx: Dict[Any, str]) -> List[Dict[str, Any]]:
    tables = ["models", "modelos"]
    for t in tables:
        if mysql_table_exists(conn, t):
            cols = mysql_columns(conn, t)
            id_col = pick_first_present(cols, ["id", "Id", "id_modelo", "IdModelo"]) or "id"
            marca_col = pick_first_present(cols, ["marca_id", "id_marca", "brand_id", "IdMarcas"]) or "marca_id"
            name_col = pick_first_present(cols, ["nombre", "Nombre", "name", "modelo"]) or "nombre"
            alias_col = pick_first_present(cols, ["alias", "Alias"])  # opcional
            tipo_name_col = pick_first_present(cols, ["tipo_equipo", "tipo", "modelo_tipo", "tipoEquipo"])  # str
            tipo_id_col = pick_first_present(cols, ["tipo_equipo_id", "id_tipo_equipo", "IdEquipos"])  # id -> equipos
            variante_col = pick_first_present(cols, ["variante", "modelo_variante"])  # opcional
            with conn.cursor() as cur:
                sel_cols = [
                    f"`{id_col}` AS id",
                    f"`{marca_col}` AS marca_id",
                    f"`{name_col}` AS nombre",
                ]
                if alias_col:
                    sel_cols.append(f"`{alias_col}` AS alias")
                if tipo_name_col:
                    sel_cols.append(f"`{tipo_name_col}` AS tipo_equipo")
                if tipo_id_col:
                    sel_cols.append(f"`{tipo_id_col}` AS tipo_equipo_id")
                if variante_col:
                    sel_cols.append(f"`{variante_col}` AS variante")
                sel = f"SELECT {', '.join(sel_cols)} FROM `{t}`"
                cur.execute(sel)
                rows = cur.fetchall()
                # Resolver tipo_equipo desde id si aplica
                for r in rows:
                    if not r.get("tipo_equipo") and r.get("tipo_equipo_id") is not None:
                        r["tipo_equipo"] = equipos_idx.get(r.get("tipo_equipo_id"))
                return rows
    return []


def fetch_proveedores(conn) -> List[Dict[str, Any]]:
    tables = ["proveedores_externos", "proveedores", "proveedores_servicio"]
    for t in tables:
        if mysql_table_exists(conn, t):
            cols = mysql_columns(conn, t)
            id_col = pick_first_present(cols, ["id", "Id", "id_proveedor", "IdProveedor"]) or "id"
            name_col = pick_first_present(cols, ["nombre", "Nombre", "name"]) or "nombre"
            with conn.cursor() as cur:
                sel = f"SELECT `{id_col}` AS id, `{name_col}` AS nombre FROM `{t}`"
                cur.execute(sel)
                return cur.fetchall()
    return []


# ------------- PostgreSQL inserciones -------------

def insert_rows(conn, table: str, columns: List[str], rows: Iterable[Iterable[Any]]):
    id_in_cols = "id" in columns
    cols_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    overriding = " OVERRIDING SYSTEM VALUE" if id_in_cols else ""
    # Ignorar conflictos por cualquier índice único para evitar duplicados por nombre
    conflict = " ON CONFLICT DO NOTHING"
    sql = f"INSERT INTO {table} ({cols_sql}){overriding} VALUES ({placeholders}){conflict}"
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
        if id_in_cols:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}','id'), (SELECT COALESCE(MAX(id),0) FROM {table}), true)"
            )


def get_or_create(conn, table: str, where_sql: str, where_params: List[Any], insert_cols: List[str], insert_vals: List[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {table} WHERE {where_sql} LIMIT 1", where_params)
        row = cur.fetchone()
        if row:
            return int(row[0])
        cols = ", ".join(insert_cols)
        placeholders = ", ".join(["%s"] * len(insert_cols))
        cur.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING RETURNING id",
            insert_vals,
        )
        got = cur.fetchone()
        if got:
            return int(got[0])
        # Si hubo conflicto, volver a seleccionar
        cur.execute(f"SELECT id FROM {table} WHERE {where_sql} LIMIT 1", where_params)
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"No se pudo crear fila en {table}")
        return int(row[0])


def normalize_str(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s2 = str(s).strip()
    return s2 if s2 else None


def main():
    mysql_conn = connect_mysql()
    pg_conn = connect_pg()
    # Aislar en una transacción grande para atomicidad
    with pg_conn.transaction():
        # 1) Clientes
        customers = fetch_customers(mysql_conn)
        if customers:
            rows = []
            for r in customers:
                rid = r.get("id")
                name = normalize_str(r.get("razon_social") or r.get("nombre"))
                if not name:
                    continue
                rows.append([rid, name])
            insert_rows(pg_conn, "customers", ["id", "razon_social"], rows)

        # 2) Marcas
        marcas = fetch_marcas(mysql_conn)
        if marcas:
            rows = []
            for r in marcas:
                rid = r.get("id")
                nombre = normalize_str(r.get("nombre"))
                if not nombre:
                    continue
                rows.append([rid, nombre])
            insert_rows(pg_conn, "marcas", ["id", "nombre"], rows)

        # 3) Tipos de equipo (catálogo general)
        equipos_rows, equipos_idx = fetch_equipos(mysql_conn)
        if equipos_rows:
            rows = []
            for r in equipos_rows:
                rid = r.get("id")
                nombre = normalize_str(r.get("nombre"))
                if not nombre:
                    continue
                rows.append([rid, nombre, True])
            insert_rows(pg_conn, "catalogo_tipos_equipo", ["id", "nombre", "activo"], rows)

        # 4) Modelos (y preparación para jerarquía)
        models = fetch_models(mysql_conn, equipos_idx)
        if models:
            mdl_rows = []
            for r in models:
                rid = r.get("id")
                marca_id = r.get("marca_id")
                nombre = normalize_str(r.get("nombre"))
                tipo_equipo = normalize_str(r.get("tipo_equipo"))
                alias = normalize_str(r.get("alias"))  # ignorado en tabla models
                variante = normalize_str(r.get("variante"))
                if not nombre or not marca_id:
                    continue
                mdl_rows.append([rid, marca_id, nombre, tipo_equipo, variante])
            insert_rows(pg_conn, "models", ["id", "marca_id", "nombre", "tipo_equipo", "variante"], mdl_rows)

            # 4b) Construir catálogo jerárquico por marca/tipo/serie/variante a partir de models
            for r in models:
                marca_id = r.get("marca_id")
                model_id = r.get("id")
                nombre = normalize_str(r.get("nombre"))
                tipo_equipo = normalize_str(r.get("tipo_equipo")) or "SIN TIPO"
                variante = normalize_str(r.get("variante"))
                if not nombre or not marca_id or not model_id:
                    continue

                # tipo por marca
                tipo_id = get_or_create(
                    pg_conn,
                    "marca_tipos_equipo",
                    "marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                    [marca_id, tipo_equipo],
                    ["marca_id", "nombre", "activo"],
                    [marca_id, tipo_equipo, True],
                )

                # serie (modelo) por tipo
                serie_id = get_or_create(
                    pg_conn,
                    "marca_series",
                    "marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                    [marca_id, tipo_id, nombre],
                    ["marca_id", "tipo_id", "nombre", "activo"],
                    [marca_id, tipo_id, nombre, True],
                )

                # variante (opcional)
                variante_id = None
                if variante:
                    variante_id = get_or_create(
                        pg_conn,
                        "marca_series_variantes",
                        "marca_id=%s AND tipo_id=%s AND serie_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                        [marca_id, tipo_id, serie_id, variante],
                        ["marca_id", "tipo_id", "serie_id", "nombre", "activo"],
                        [marca_id, tipo_id, serie_id, variante, True],
                    )

                # model_hierarchy
                full_name = f"{tipo_equipo} | {nombre}{(' ' + variante) if variante else ''}"
                get_or_create(
                    pg_conn,
                    "model_hierarchy",
                    "model_id=%s",
                    [model_id],
                    ["model_id", "marca_id", "tipo_id", "serie_id", "variante_id", "full_name"],
                    [model_id, marca_id, tipo_id, serie_id, variante_id, full_name],
                )

        # 5) Proveedores externos
        proveedores = fetch_proveedores(mysql_conn)
        if proveedores:
            rows = []
            for r in proveedores:
                rid = r.get("id")
                nombre = normalize_str(r.get("nombre"))
                if not nombre:
                    continue
                rows.append([rid, nombre])
            insert_rows(pg_conn, "proveedores_externos", ["id", "nombre"], rows)

    # fin transaction
    pg_conn.commit()
    mysql_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    try:
        main()
        print("Importación de catálogos completada.")
    except Exception as exc:
        print(f"Error en importación: {exc}")
        sys.exit(1)
