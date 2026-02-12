"""
Carga catálogos (clientes, marcas, modelos, tipos de equipo, jerarquía y proveedores)
desde CSVs ubicados en etl/out/*_access.csv hacia PostgreSQL.

Archivos esperados (si faltan, el paso se omite):
  - etl/out/customers.csv                      (id?, cod_empresa?, razon_social, ...)
  - etl/out/marcas_access.csv                  (nombre)
  - etl/out/models_access.csv                  (marca_nombre, nombre)
  - etl/out/model_tipo_equipo_access.csv       (marca_nombre, modelo_nombre, tipo_equipo)
  - etl/out/proveedores_externos_access.csv    (nombre, contacto?)

Requiere: psycopg (ya incluido en requirements del API)

Uso:
  POSTGRES_* en el entorno y:
    python etl/mysql_to_pg/import_catalogs_from_csv.py
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg


BASE = Path(__file__).resolve().parent.parent.parent / "etl" / "out"


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


def norm(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = str(s).strip()
    return s if s else None


def get_field(row: Dict[str, Any], candidates: List[str]) -> Optional[str]:
    if not row:
        return None
    norm_targets = [c.strip().lower() for c in candidates]
    for k, v in row.items():
        key = str(k).strip().lstrip("\ufeff").lower()
        if key in norm_targets:
            return v
    # fallback: si solo hay una columna
    if len(row) == 1:
        return next(iter(row.values()))
    return None


def insert_rows(conn, table: str, columns: List[str], rows: Iterable[Iterable[Any]]):
    id_in_cols = "id" in columns
    cols_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    conflict = " ON CONFLICT DO NOTHING"
    overriding = " OVERRIDING SYSTEM VALUE" if id_in_cols else ""
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


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        return reader.fieldnames or [], rows


def load_customers(conn):
    hdr, rows = read_csv(BASE / "customers.csv")
    if not rows:
        return
    seen = set()
    out = []
    for r in rows:
        name = norm(
            get_field(r, ["razon_social", "razonsocial", "razon", "nombre", "company"])  # robustez BOM
        )
        if not name:
            continue
        key = name.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append([name])
    if out:
        # insertar de forma idempotente por razon_social (normalizada)
        for [name] in out:
            get_or_create(
                conn,
                "customers",
                "UPPER(TRIM(razon_social))=UPPER(TRIM(%s))",
                [name],
                ["razon_social"],
                [name],
            )

    # Completar detalles si existen columnas adicionales en CSV
    hdr_lower = [h.strip().lstrip("\ufeff").lower() for h in hdr]
    has_any_detail = any(k in hdr_lower for k in ["cod_empresa","cuit","contacto","telefono","telefono_2","email"])
    if has_any_detail:
        with (BASE / "customers.csv").open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                razon = norm(get_field(r, ["razon_social", "razonsocial", "razon", "nombre", "company"]))
                if not razon:
                    continue
                cod_empresa = norm(get_field(r, ["cod_empresa"]))
                cuit = norm(get_field(r, ["cuit"]))
                contacto = norm(get_field(r, ["contacto"]))
                tel = norm(get_field(r, ["telefono"]))
                tel2 = norm(get_field(r, ["telefono_2","telefono2"]))
                email = norm(get_field(r, ["email"]))
                sets = []
                vals: List[Any] = []
                if cod_empresa is not None:
                    sets.append("cod_empresa=%s")
                    vals.append(cod_empresa)
                if cuit is not None:
                    sets.append("cuit=%s")
                    vals.append(cuit)
                if contacto is not None:
                    sets.append("contacto=%s")
                    vals.append(contacto)
                if tel is not None:
                    sets.append("telefono=%s")
                    vals.append(tel)
                if tel2 is not None:
                    sets.append("telefono_2=%s")
                    vals.append(tel2)
                if email is not None:
                    sets.append("email=%s")
                    vals.append(email)
                if not sets:
                    continue
                vals.append(razon)
                sql = f"UPDATE customers SET {', '.join(sets)} WHERE UPPER(TRIM(razon_social))=UPPER(TRIM(%s))"
                with conn.cursor() as cur:
                    cur.execute(sql, vals)


def load_marcas(conn) -> Dict[str, int]:
    hdr, rows = read_csv(BASE / "marcas_access.csv")
    seen = set()
    out = []
    for r in rows:
        nombre = norm(get_field(r, ["nombre", "brand", "marca"]))
        if not nombre:
            continue
        key = nombre.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append([nombre])
    if out:
        insert_rows(conn, "marcas", ["nombre"], out)
    # construir índice nombre->id
    idx: Dict[str, int] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, nombre FROM marcas")
        for rid, nombre in cur.fetchall():
            idx[str(nombre).strip().upper()] = int(rid)
    return idx


def load_models(conn, marca_idx: Dict[str, int]) -> Tuple[Dict[Tuple[int, str], int], Dict[Tuple[int, str], Tuple[str, List[str]]]]:
    hdr, rows = read_csv(BASE / "models_access.csv")
    # Inserción en models y captura de variantes si existen en este CSV
    variantes_map: Dict[Tuple[int, str], Tuple[str, List[str]]] = {}
    for r in rows:
        marca_nombre = norm(get_field(r, ["marca_nombre", "brand", "marca"]))
        modelo = norm(get_field(r, ["nombre", "modelo", "model"]))
        variante = norm(get_field(r, ["variante", "modelo_variante", "variant"]))
        variantes_field = get_field(r, ["variantes", "lista_variantes", "variants"]) or ""
        variantes_list: List[str] = []
        if variantes_field:
            raw = [x.strip() for x in re.split(r"[;,|]", str(variantes_field))]
            variantes_list.extend([v for v in raw if v])
        if variante:
            # asegurar que la variante única también se incluya
            if variante not in variantes_list:
                variantes_list.append(variante)
        if not marca_nombre or not modelo:
            continue
        marca_id = marca_idx.get(marca_nombre.upper())
        if not marca_id:
            # crear marca al vuelo
            marca_id = get_or_create(
                conn,
                "marcas",
                "UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                [marca_nombre],
                ["nombre"],
                [marca_nombre],
            )
            marca_idx[marca_nombre.upper()] = marca_id
        get_or_create(
            conn,
            "models",
            "marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
            [marca_id, modelo],
            ["marca_id", "nombre"],
            [marca_id, modelo],
        )
        if variantes_list:
            key = (marca_id, modelo.upper())
            # Acumular si ya había variantes previas para el mismo modelo
            if key in variantes_map:
                base_modelo, prev = variantes_map[key]
                merged = list(dict.fromkeys(prev + variantes_list))
                variantes_map[key] = (base_modelo, merged)
            else:
                variantes_map[key] = (modelo, variantes_list)
    # índice (marca_id, modelo)->model_id
    idx: Dict[Tuple[int, str], int] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, marca_id, nombre FROM models")
        for mid, bid, nombre in cur.fetchall():
            idx[(int(bid), str(nombre).strip().upper())] = int(mid)
    return idx, variantes_map


def load_model_tipos(conn, marca_idx: Dict[str, int], model_idx: Dict[Tuple[int, str], int]):
    hdr, rows = read_csv(BASE / "model_tipo_equipo_access.csv")
    if not rows:
        return
    tipos_seen = set()
    # 1) catalogo_tipos_equipo
    for r in rows:
        tipo = norm(get_field(r, ["tipo_equipo", "tipo", "equipment_type"]))
        if not tipo:
            continue
        key = tipo.upper()
        if key in tipos_seen:
            continue
        tipos_seen.add(key)
        insert_rows(conn, "catalogo_tipos_equipo", ["nombre", "activo"], [[tipo, True]])

    # 2) actualizar models.tipo_equipo y construir jerarquía
    for r in rows:
        marca_nombre = norm(get_field(r, ["marca_nombre", "brand", "marca"]))
        modelo_nombre = norm(get_field(r, ["modelo_nombre", "nombre", "modelo", "model"]))
        tipo_equipo = norm(get_field(r, ["tipo_equipo", "tipo", "equipment_type"])) or "SIN TIPO"
        if not marca_nombre or not modelo_nombre:
            continue
        bid = marca_idx.get(marca_nombre.upper())
        if not bid:
            continue
        mid = model_idx.get((bid, modelo_nombre.upper()))
        if not mid:
            # si no existe el modelo, crearlo y reintentar
            mid = get_or_create(
                conn,
                "models",
                "marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                [bid, modelo_nombre],
                ["marca_id", "nombre"],
                [bid, modelo_nombre],
            )
            model_idx[(bid, modelo_nombre.upper())] = mid

        # actualizar models.tipo_equipo
        with conn.cursor() as cur:
            cur.execute("UPDATE models SET tipo_equipo=%s WHERE id=%s", (tipo_equipo, mid))

        # tipo por marca
        tipo_id = get_or_create(
            conn,
            "marca_tipos_equipo",
            "marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
            [bid, tipo_equipo],
            ["marca_id", "nombre", "activo"],
            [bid, tipo_equipo, True],
        )
        # serie por tipo (modelo como serie)
        serie_id = get_or_create(
            conn,
            "marca_series",
            "marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
            [bid, tipo_id, modelo_nombre],
            ["marca_id", "tipo_id", "nombre", "activo"],
            [bid, tipo_id, modelo_nombre, True],
        )
        # model_hierarchy
        full_name = f"{tipo_equipo} | {modelo_nombre}"
        get_or_create(
            conn,
            "model_hierarchy",
            "model_id=%s",
            [mid],
            ["model_id", "marca_id", "tipo_id", "serie_id", "variante_id", "full_name"],
            [mid, bid, tipo_id, serie_id, None, full_name],
        )


def load_model_variantes(conn, marca_idx: Dict[str, int], model_idx: Dict[Tuple[int, str], int]):
    # Opcional: models_variante_access.csv con columnas: marca_nombre, modelo_nombre, variante
    path = BASE / "models_variante_access.csv"
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            marca_nombre = norm(get_field(r, ["marca_nombre", "marca", "brand"]))
            modelo_nombre = norm(get_field(r, ["modelo_nombre", "modelo", "nombre", "model"]))
            variante = norm(get_field(r, ["variante", "variant"]))
            if not marca_nombre or not modelo_nombre or not variante:
                continue
            bid = marca_idx.get(marca_nombre.upper())
            if not bid:
                continue
            mid = model_idx.get((bid, modelo_nombre.upper()))
            if not mid:
                # crear modelo si no existe
                mid = get_or_create(
                    conn,
                    "models",
                    "marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                    [bid, modelo_nombre],
                    ["marca_id", "nombre"],
                    [bid, modelo_nombre],
                )
                model_idx[(bid, modelo_nombre.upper())] = mid
            # Recuperar o crear tipo/serie a partir de model_hierarchy o por defecto
            with conn.cursor() as cur:
                cur.execute("SELECT tipo_id, serie_id FROM model_hierarchy WHERE model_id=%s", (mid,))
                row = cur.fetchone()
            if row:
                tipo_id, serie_id = row
            else:
                # fallback: crear tipo 'SIN TIPO' y serie igual al modelo
                tipo_id = get_or_create(
                    conn,
                    "marca_tipos_equipo",
                    "marca_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                    [bid, "SIN TIPO"],
                    ["marca_id", "nombre", "activo"],
                    [bid, "SIN TIPO", True],
                )
                serie_id = get_or_create(
                    conn,
                    "marca_series",
                    "marca_id=%s AND tipo_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                    [bid, tipo_id, modelo_nombre],
                    ["marca_id", "tipo_id", "nombre", "activo"],
                    [bid, tipo_id, modelo_nombre, True],
                )
            variante_id = get_or_create(
                conn,
                "marca_series_variantes",
                "marca_id=%s AND tipo_id=%s AND serie_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                [bid, tipo_id, serie_id, variante],
                ["marca_id", "tipo_id", "serie_id", "nombre", "activo"],
                [bid, tipo_id, serie_id, variante, True],
            )
            # Obtener nombre del tipo para full_name consistente
            with conn.cursor() as cur:
                cur.execute("SELECT nombre FROM marca_tipos_equipo WHERE id=%s", (tipo_id,))
                row = cur.fetchone()
            tipo_nombre = row[0] if row else ""
            full_name = f"{tipo_nombre} | {modelo_nombre} {variante}".strip()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE model_hierarchy SET variante_id=%s, full_name=%s WHERE model_id=%s",
                    (variante_id, full_name, mid),
                )


def apply_variants_map(conn, model_idx: Dict[Tuple[int, str], int], variantes_map: Dict[Tuple[int, str], Tuple[str, List[str]]]):
    if not variantes_map:
        return
    for (bid, modelo_upper), (modelo_nombre, variantes) in variantes_map.items():
        mid = model_idx.get((bid, modelo_upper))
        if not mid:
            continue
        with conn.cursor() as cur:
            cur.execute("SELECT tipo_id, serie_id FROM model_hierarchy WHERE model_id=%s", (mid,))
            row = cur.fetchone()
        if not row:
            continue  # requiere que se haya armado jerarquía por tipos antes
        tipo_id, serie_id = row
        # para múltiples variantes, actualizamos la jerarquía del modelo con la última por conveniencia
        last_variant_id = None
        last_full = None
        for variante in variantes:
            variante_id = get_or_create(
                conn,
                "marca_series_variantes",
                "marca_id=%s AND tipo_id=%s AND serie_id=%s AND UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
                [bid, tipo_id, serie_id, variante],
                ["marca_id", "tipo_id", "serie_id", "nombre", "activo"],
                [bid, tipo_id, serie_id, variante, True],
            )
            with conn.cursor() as cur:
                cur.execute("SELECT nombre FROM marca_tipos_equipo WHERE id=%s", (tipo_id,))
                r = cur.fetchone()
            tipo_nombre = r[0] if r else ""
            full_name = f"{tipo_nombre} | {modelo_nombre} {variante}".strip()
            last_variant_id = variante_id
            last_full = full_name
        if last_variant_id is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE model_hierarchy SET variante_id=%s, full_name=%s WHERE model_id=%s",
                    (last_variant_id, last_full, mid),
                )


def load_proveedores(conn):
    hdr, rows = read_csv(BASE / "proveedores_externos_access.csv")
    if not rows:
        return
    for r in rows:
        nombre = norm(get_field(r, ["nombre", "name"]))
        if not nombre:
            continue
        pid = get_or_create(
            conn,
            "proveedores_externos",
            "UPPER(TRIM(nombre))=UPPER(TRIM(%s))",
            [nombre],
            ["nombre"],
            [nombre],
        )
        contacto = norm(get_field(r, ["contacto", "contact"]))
        telefono = norm(get_field(r, ["telefono", "phone"]))
        email = norm(get_field(r, ["email"]))
        direccion = norm(get_field(r, ["direccion", "address"]))
        notas = norm(get_field(r, ["notas", "notes"]))
        sets = []
        vals: List[Any] = []
        if contacto is not None:
            sets.append("contacto=%s")
            vals.append(contacto)
        if telefono is not None:
            sets.append("telefono=%s")
            vals.append(telefono)
        if email is not None:
            sets.append("email=%s")
            vals.append(email)
        if direccion is not None:
            sets.append("direccion=%s")
            vals.append(direccion)
        if notas is not None:
            sets.append("notas=%s")
            vals.append(notas)
        if sets:
            vals.append(pid)
            with conn.cursor() as cur:
                cur.execute(f"UPDATE proveedores_externos SET {', '.join(sets)} WHERE id=%s", vals)


def _slug(s: str) -> str:
    import unicodedata, re
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "tec"


def load_tecnicos(conn):
    path = BASE / "tecnicos_access.csv"
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            nombre = norm(get_field(r, ["nombre"]))
            if not nombre:
                continue
            baja = (get_field(r, ["baja"]) or "0").strip()
            try:
                baja_val = int(baja)
            except Exception:
                baja_val = 0
            activo = not bool(baja_val)
            # correo sintético único
            rid = norm(get_field(r, ["id_tecnico","id"])) or "0"
            local = f"{_slug(nombre)}-{rid}"
            email = f"{local}@local.invalid"
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users(nombre, email, rol, activo, perm_ingresar)
                    VALUES (%s,%s,'tecnico',%s,FALSE)
                    ON CONFLICT DO NOTHING
                    """,
                    (nombre, email, activo),
                )


def main():
    conn = connect_pg()
    with conn.transaction():
        load_customers(conn)
        marca_idx = load_marcas(conn)
        model_idx, variantes_map = load_models(conn, marca_idx)
        load_model_tipos(conn, marca_idx, model_idx)
        apply_variants_map(conn, model_idx, variantes_map)
        load_model_variantes(conn, marca_idx, model_idx)
        load_proveedores(conn)
        load_tecnicos(conn)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
