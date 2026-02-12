"""
Importa ingresos (delta) y relacionados desde MySQL a PostgreSQL.

Sin argumentos: detecta ingresos faltantes en PG (comparando IDs) y los importa.
Con argumentos: lista de IDs de ingreso a importar (separados por espacio).

Requisitos: PyMySQL, psycopg
Usa variables de entorno MYSQL_* y POSTGRES_* (como otros scripts del ETL).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import pymysql  # type: ignore
import psycopg


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def connect_mysql():
    return pymysql.connect(
        host=env("MYSQL_HOST", "127.0.0.1"),
        port=int(env("MYSQL_PORT", "3306") or 3306),
        user=env("MYSQL_USER", "root"),
        password=env("MYSQL_PASSWORD", ""),
        database=env("MYSQL_DATABASE", env("MYSQL_DB", "servicio_tecnico")),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def connect_pg():
    dsn = (
        f"host={env('POSTGRES_HOST','127.0.0.1')} "
        f"port={env('POSTGRES_PORT','5432')} "
        f"dbname={env('POSTGRES_DB','servicio_tecnico')} "
        f"user={env('POSTGRES_USER','sepid')} "
        f"password={env('POSTGRES_PASSWORD','')}"
    )
    return psycopg.connect(dsn)


def get_or_create(cur, table: str, where_sql: str, where_params: List[Any], insert_cols: List[str], insert_vals: List[Any]) -> int:
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
    cur.execute(f"SELECT id FROM {table} WHERE {where_sql} LIMIT 1", where_params)
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"No se pudo crear fila en {table}")
    return int(row[0])


def to_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    try:
        return bool(int(v))
    except Exception:
        s = str(v).strip().lower()
        if s in ("true","t","1","yes","y"): return True
        if s in ("false","f","0","no","n"): return False
        return None


def simp(s: Optional[str]) -> str:
    if not isinstance(s, str):
        return ""
    import unicodedata
    s2 = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return " ".join(s2.strip().lower().split())


def enum_label_mapper(cur_pg, type_name: str):
    cur_pg.execute(
        """
        SELECT e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE t.typname = %s
        """,
        (type_name,),
    )
    rows = cur_pg.fetchall()
    import re
    label_map = {}
    ascii_map = {}
    for (label,) in rows:
        s = simp(label)
        label_map[s] = label
        ascii_map[re.sub(r"[^a-z]", "", s)] = label
    def _map(val: Optional[str]) -> Optional[str]:
        if val is None:
            return None
        s = simp(val)
        if s in label_map:
            return label_map[s]
        key = re.sub(r"[^a-z]", "", s)
        if key in ascii_map:
            return ascii_map[key]
        # inicio/coincidencia parcial
        for k, v in ascii_map.items():
            if k and key.startswith(k[:6]):
                return v
        return None
    return _map

def fetch_missing_ingreso_ids(my, pg) -> List[int]:
    with my.cursor() as cur:
        cur.execute("SELECT id FROM ingresos")
        my_ids = {int(r["id"]) for r in cur.fetchall()}  # type: ignore[index]
    with pg.cursor() as cur:
        cur.execute("SELECT id FROM ingresos")
        pg_ids = {int(r[0]) for r in cur.fetchall()}
    return sorted(list(my_ids - pg_ids))


def ensure_customer(cur_pg, my, customer_id: Optional[int]) -> int:
    if not customer_id:
        # crear placeholder si faltara (no debería ocurrir)
        return get_or_create(cur_pg, "customers", "UPPER(TRIM(razon_social))=UPPER(TRIM(%s))", ["MIGRACION"], ["razon_social"], ["MIGRACION"])
    with my.cursor() as cur:
        cur.execute("DESCRIBE customers")
        cols = [c["Field"].lower() for c in cur.fetchall()]
        name_col = "razon_social" if "razon_social" in cols else ("nombre" if "nombre" in cols else cols[0])
        cur.execute(f"SELECT `{name_col}` AS rs FROM customers WHERE id=%s", (customer_id,))
        r = cur.fetchone()
    name = (r["rs"] or "").strip() if r else "MIGRACION"  # type: ignore[index]
    return get_or_create(cur_pg, "customers", "UPPER(TRIM(razon_social))=UPPER(TRIM(%s))", [name], ["razon_social"], [name])


def pg_brand_map(cur_pg) -> Dict[str, int]:
    cur_pg.execute("SELECT id, nombre FROM marcas")
    return {str(n).strip().upper(): int(i) for (i, n) in cur_pg.fetchall()}


def pg_model_map(cur_pg) -> Dict[Tuple[int, str], int]:
    cur_pg.execute("SELECT id, marca_id, nombre FROM models")
    return {(int(b), str(n).strip().upper()): int(i) for (i, b, n) in cur_pg.fetchall()}


def ensure_device(cur_pg, my, device_id: int, brand_map: Dict[str, int], model_map: Dict[Tuple[int, str], int]) -> int:
    # ya existe?
    cur_pg.execute("SELECT id FROM devices WHERE id=%s", (device_id,))
    row = cur_pg.fetchone()
    if row:
        return int(row[0])
    # traer device de MySQL
    with my.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.customer_id, d.marca_id, d.model_id, d.numero_serie,
                   d.garantia_bool, d.propietario, d.etiq_garantia_ok, d.n_de_control,
                   m.nombre AS marca_nombre, mo.nombre AS modelo_nombre
            FROM devices d
            LEFT JOIN marcas m ON m.id = d.marca_id
            LEFT JOIN models mo ON mo.id = d.model_id
            WHERE d.id = %s
            """,
            (device_id,),
        )
        r = cur.fetchone()
    if not r:
        # crear stub mínimo: requiere customer
        cust_id = ensure_customer(cur_pg, my, None)
        cur_pg.execute(
            "INSERT INTO devices(id, customer_id) OVERRIDING SYSTEM VALUE VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (device_id, cust_id),
        )
        return device_id
    cust_id = ensure_customer(cur_pg, my, r.get("customer_id"))  # type: ignore[attr-defined]
    marca_nombre = (r.get("marca_nombre") or "").strip().upper()
    modelo_nombre = (r.get("modelo_nombre") or "").strip()
    pg_marca_id = brand_map.get(marca_nombre)
    pg_model_id = None
    if pg_marca_id:
        pg_model_id = model_map.get((pg_marca_id, modelo_nombre.upper()))
    cur_pg.execute(
        """
        INSERT INTO devices(id, customer_id, marca_id, model_id, numero_serie, garantia_bool, propietario, etiq_garantia_ok, n_de_control)
        OVERRIDING SYSTEM VALUE
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING
        """,
        (
            r.get("id"),
            cust_id,
            pg_marca_id,
            pg_model_id,
            r.get("numero_serie"),
            to_bool(r.get("garantia_bool")),
            r.get("propietario"),
            to_bool(r.get("etiq_garantia_ok")),
            r.get("n_de_control"),
        ),
    )
    return int(r.get("id"))


def map_user_by_name(cur_pg, my_user_id: Optional[int], my) -> Optional[int]:
    if not my_user_id:
        return None
    with my.cursor() as cur:
        cur.execute("SELECT nombre, email FROM users WHERE id=%s", (my_user_id,))
        r = cur.fetchone()
    if not r:
        return None
    nombre = (r.get("nombre") or "").strip()
    email = (r.get("email") or "").strip()
    # intentar por email primero
    cur_pg.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1", (email,))
    a = cur_pg.fetchone()
    if a:
        return int(a[0])
    # luego por nombre
    cur_pg.execute("SELECT id FROM users WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s)) LIMIT 1", (nombre,))
    b = cur_pg.fetchone()
    return int(b[0]) if b else None


def map_location_id(cur_pg, my, loc_id: Optional[int]) -> Optional[int]:
    if not loc_id:
        return None
    with my.cursor() as cur:
        cur.execute("SELECT nombre FROM locations WHERE id=%s", (loc_id,))
        r = cur.fetchone()
    if not r:
        return None
    nombre = (r.get("nombre") or "").strip()
    # buscar por nombre en PG
    cur_pg.execute("SELECT id FROM locations WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", (nombre,))
    a = cur_pg.fetchone()
    return int(a[0]) if a else None


def ensure_migracion_user(cur_pg) -> int:
    cur_pg.execute("SELECT id FROM users WHERE email='migracion@local.invalid' LIMIT 1")
    r = cur_pg.fetchone()
    if r:
        return int(r[0])
    cur_pg.execute(
        "INSERT INTO users(nombre, email, rol, activo, perm_ingresar) VALUES (%s,%s,%s,TRUE,FALSE) RETURNING id",
        ("MIGRACION", "migracion@local.invalid", "tecnico"),
    )
    return int(cur_pg.fetchone()[0])


def import_delta(ids: List[int]):
    my = connect_mysql()
    pg = connect_pg()
    try:
        with pg.transaction():
            with pg.cursor() as cur_pg:
                brand_map = pg_brand_map(cur_pg)
                model_map = pg_model_map(cur_pg)
                map_ticket = enum_label_mapper(cur_pg, 'ticket_state')
                map_motivo = enum_label_mapper(cur_pg, 'motivo_ingreso')
                map_dispo = enum_label_mapper(cur_pg, 'disposicion_type')
                map_quote = enum_label_mapper(cur_pg, 'quote_estado')
                for ingreso_id in ids:
                    # traer ingreso desde MySQL
                    with my.cursor() as cur:
                        cur.execute("SELECT * FROM ingresos WHERE id=%s", (ingreso_id,))
                        inc = cur.fetchone()
                    if not inc:
                        continue
                    device_id = int(inc.get("device_id")) if inc.get("device_id") is not None else None
                    if not device_id:
                        continue
                    # asegurar device
                    dev_id = ensure_device(cur_pg, my, device_id, brand_map, model_map)
                    # mapear usuarios y ubicación
                    pg_recibido = map_user_by_name(cur_pg, inc.get("recibido_por"), my)
                    pg_asignado = map_user_by_name(cur_pg, inc.get("asignado_a"), my)
                    pg_loc = map_location_id(cur_pg, my, inc.get("ubicacion_id"))
                    # insertar ingreso
                    cur_pg.execute(
                        """
                        INSERT INTO ingresos (
                          id, device_id, estado, motivo, fecha_ingreso, fecha_creacion, fecha_servicio,
                          ubicacion_id, disposicion, informe_preliminar, accesorios, equipo_variante,
                          remito_ingreso, remito_salida, factura_numero, recibido_por, comentarios,
                          garantia_reparacion, faja_garantia, presupuesto_estado, asignado_a, etiqueta_qr,
                          alquilado, alquiler_a, alquiler_remito, alquiler_fecha,
                          propietario_nombre, propietario_contacto, propietario_doc,
                          descripcion_problema, trabajos_realizados, resolucion, fecha_entrega
                        ) OVERRIDING SYSTEM VALUE
                        VALUES (
                          %s, %s, %s::ticket_state, %s::motivo_ingreso, %s, %s, %s,
                          %s, %s::disposicion_type, %s, %s, %s,
                          %s, %s, %s, %s, %s,
                          %s, %s, %s::quote_estado, %s, %s,
                          %s, %s, %s, %s,
                          %s, %s, %s,
                          %s, %s, %s, %s
                        ) ON CONFLICT DO NOTHING
                        """,
                        (
                            ingreso_id,
                            dev_id,
                            map_ticket(inc.get("estado")) or inc.get("estado"),
                            map_motivo(inc.get("motivo")) or inc.get("motivo"),
                            inc.get("fecha_ingreso"),
                            inc.get("fecha_creacion"),
                            inc.get("fecha_servicio"),
                            pg_loc,
                            map_dispo(inc.get("disposicion")) or inc.get("disposicion"),
                            inc.get("informe_preliminar"),
                            inc.get("accesorios"),
                            inc.get("equipo_variante"),
                            inc.get("remito_ingreso"),
                            inc.get("remito_salida"),
                            inc.get("factura_numero"),
                            pg_recibido,
                            inc.get("comentarios"),
                            to_bool(inc.get("garantia_reparacion")),
                            inc.get("faja_garantia"),
                            map_quote(inc.get("presupuesto_estado")) or inc.get("presupuesto_estado"),
                            pg_asignado,
                            inc.get("etiqueta_qr"),
                            to_bool(inc.get("alquilado")),
                            inc.get("alquiler_a"),
                            inc.get("alquiler_remito"),
                            inc.get("alquiler_fecha"),
                            inc.get("propietario_nombre"),
                            inc.get("propietario_contacto"),
                            inc.get("propietario_doc"),
                            inc.get("descripcion_problema"),
                            inc.get("trabajos_realizados"),
                            inc.get("resolucion"),
                            inc.get("fecha_entrega"),
                        ),
                    )

                    # quotes
                    with my.cursor() as cur:
                        cur.execute("SELECT * FROM quotes WHERE ingreso_id=%s", (ingreso_id,))
                        qrow = cur.fetchone()
                    if qrow:
                        cur_pg.execute(
                            """
                            INSERT INTO quotes (id, ingreso_id, estado, moneda, subtotal, autorizado_por, forma_pago, fecha_emitido, fecha_aprobado, pdf_url)
                            OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s::quote_estado,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                qrow.get("id"), qrow.get("ingreso_id"), qrow.get("estado"), qrow.get("moneda"), qrow.get("subtotal"),
                                qrow.get("autorizado_por"), qrow.get("forma_pago"), qrow.get("fecha_emitido"), qrow.get("fecha_aprobado"), qrow.get("pdf_url"),
                            ),
                        )
                        # items
                        with my.cursor() as cur:
                            cur.execute("SELECT * FROM quote_items WHERE quote_id=%s", (qrow.get("id"),))
                            items = cur.fetchall()
                        for it in items:
                            cur_pg.execute(
                                """
                                INSERT INTO quote_items(id, quote_id, tipo, descripcion, qty, precio_u, repuesto_id)
                                OVERRIDING SYSTEM VALUE
                                VALUES (%s,%s,%s::quote_item_tipo,%s,%s,%s,%s)
                                ON CONFLICT DO NOTHING
                                """,
                                (
                                    it.get("id"), it.get("quote_id"), it.get("tipo"), it.get("descripcion"), it.get("qty"), it.get("precio_u"), it.get("repuesto_id"),
                                ),
                            )

                    # events
                    with my.cursor() as cur:
                        cur.execute("SELECT * FROM ingreso_events WHERE ticket_id=%s", (ingreso_id,))
                        evs = cur.fetchall()
                    for ev in evs:
                        cur_pg.execute(
                            """
                            INSERT INTO ingreso_events(id, ticket_id, de_estado, a_estado, usuario_id, ts, comentario)
                            OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s::ticket_state,%s::ticket_state,%s,%s,%s)
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                ev.get("id"), ev.get("ticket_id"), ev.get("de_estado"), ev.get("a_estado"),
                                map_user_by_name(cur_pg, ev.get("usuario_id"), my), ev.get("ts"), ev.get("comentario"),
                            ),
                        )

                    # accesorios
                    with my.cursor() as cur:
                        cur.execute("SELECT * FROM ingreso_accesorios WHERE ingreso_id=%s", (ingreso_id,))
                        accs = cur.fetchall()
                    # asegurar accesorios en catálogo
                    for ac in accs:
                        acc_id = ac.get("accesorio_id")
                        if acc_id is None:
                            continue
                        cur_pg.execute("SELECT id FROM catalogo_accesorios WHERE id=%s", (acc_id,))
                        if not cur_pg.fetchone():
                            cur_pg.execute(
                                "INSERT INTO catalogo_accesorios(id, nombre, activo) VALUES (%s,%s,TRUE) ON CONFLICT DO NOTHING",
                                (acc_id, f"ACC_{acc_id}"),
                            )
                        cur_pg.execute(
                            """
                            INSERT INTO ingreso_accesorios(id, ingreso_id, accesorio_id, referencia, descripcion)
                            OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
                            """,
                            (
                                ac.get("id"), ac.get("ingreso_id"), ac.get("accesorio_id"), ac.get("referencia"), ac.get("descripcion"),
                            ),
                        )

                    # media
                    with my.cursor() as cur:
                        cur.execute("SELECT * FROM ingreso_media WHERE ingreso_id=%s", (ingreso_id,))
                        medias = cur.fetchall()
                    if medias:
                        mig_uid = ensure_migracion_user(cur_pg)
                        for m in medias:
                            uid = map_user_by_name(cur_pg, m.get("usuario_id"), my) or mig_uid
                            cur_pg.execute(
                                """
                                INSERT INTO ingreso_media(
                                  id, ingreso_id, usuario_id, storage_path, thumbnail_path, original_name,
                                  mime_type, size_bytes, width, height, comentario, created_at, updated_at
                                ) OVERRIDING SYSTEM VALUE
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT DO NOTHING
                                """,
                                (
                                    m.get("id"), m.get("ingreso_id"), uid,
                                    m.get("storage_path"), m.get("thumbnail_path"), m.get("original_name"),
                                    m.get("mime_type"), m.get("size_bytes"), m.get("width"), m.get("height"), m.get("comentario"),
                                    m.get("created_at"), m.get("updated_at"),
                                ),
                            )

                    # handoffs
                    with my.cursor() as cur:
                        cur.execute("SELECT * FROM handoffs WHERE ingreso_id=%s", (ingreso_id,))
                        hrows = cur.fetchall()
                    for h in hrows:
                        cur_pg.execute(
                            """
                            INSERT INTO handoffs(
                              id, ingreso_id, pdf_orden_salida, firmado_cliente, firmado_empresa, fecha,
                              n_factura, factura_url, orden_taller, remito_impreso, fecha_impresion_remito, impresion_remito_url
                            ) OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                h.get("id"), h.get("ingreso_id"), h.get("pdf_orden_salida"),
                                to_bool(h.get("firmado_cliente")), to_bool(h.get("firmado_empresa")), h.get("fecha"),
                                h.get("n_factura"), h.get("factura_url"), h.get("orden_taller"), to_bool(h.get("remito_impreso")),
                                h.get("fecha_impresion_remito"), h.get("impresion_remito_url"),
                            ),
                        )

                    # equipos_derivados
                    map_deriv = enum_label_mapper(cur_pg, 'deriv_estado')
                    with my.cursor() as cur:
                        cur.execute(
                            """
                            SELECT e.*, p.nombre AS proveedor_nombre
                            FROM equipos_derivados e
                            LEFT JOIN proveedores_externos p ON p.id = e.proveedor_id
                            WHERE e.ingreso_id=%s
                            """,
                            (ingreso_id,),
                        )
                        drows = cur.fetchall()
                    for d in drows:
                        prov_id = d.get("proveedor_id")
                        prov_nom = (d.get("proveedor_nombre") or f"PROV_{prov_id}") if prov_id else None
                        if prov_id:
                            cur_pg.execute("SELECT id FROM proveedores_externos WHERE id=%s", (prov_id,))
                            if not cur_pg.fetchone():
                                cur_pg.execute(
                                    "INSERT INTO proveedores_externos(id, nombre) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                                    (prov_id, prov_nom),
                                )
                        cur_pg.execute(
                            """
                            INSERT INTO equipos_derivados(
                              id, ingreso_id, proveedor_id, remit_deriv, fecha_deriv, fecha_entrega, estado, comentarios
                            ) OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s,%s,%s,%s,%s::deriv_estado,%s)
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                d.get("id"), d.get("ingreso_id"), d.get("proveedor_id"), d.get("remit_deriv"), d.get("fecha_deriv"), d.get("fecha_entrega"),
                                map_deriv(d.get("estado")) or d.get("estado"), d.get("comentarios"),
                            ),
                        )

        pg.commit()
        print(f"Import delta completo: {len(ids)} ingresos")
    finally:
        try:
            my.close()
        except Exception:
            pass
        try:
            pg.close()
        except Exception:
            pass


if __name__ == "__main__":
    ids: List[int] = []
    # Modo 1: ids por argumento
    if len(sys.argv) > 1:
        ids = [int(x) for x in sys.argv[1:] if str(x).isdigit()]
        import_delta(ids)
        sys.exit(0)
    # Modo 2: delta auto + sincronización global de relacionados
    my = connect_mysql()
    pg = connect_pg()
    try:
        # 2.a) ingresos faltantes
        ids = fetch_missing_ingreso_ids(my, pg)
        if ids:
            import_delta(ids)
        # 2.b) dispositivos faltantes
        with my.cursor() as cur:
            cur.execute("SELECT id FROM devices")
            my_devs = {int(r["id"]) for r in cur.fetchall()}  # type: ignore[index]
        with pg.cursor() as cur:
            cur.execute("SELECT id FROM devices")
            pg_devs = {int(r[0]) for r in cur.fetchall()}
        missing_devs = sorted(list(my_devs - pg_devs))
        if missing_devs:
            with pg.transaction():
                with pg.cursor() as cur_pg:
                    brand_map = pg_brand_map(cur_pg)
                    model_map = pg_model_map(cur_pg)
                    for did in missing_devs:
                        ensure_device(cur_pg, my, did, brand_map, model_map)
            pg.commit()
        # 2.c) quotes/id faltantes
        with my.cursor() as cur:
            cur.execute("SELECT id FROM quotes")
            my_q = {int(r["id"]) for r in cur.fetchall()}  # type: ignore[index]
        with pg.cursor() as cur:
            cur.execute("SELECT id FROM quotes")
            pg_q = {int(r[0]) for r in cur.fetchall()}
        missing_q = sorted(list(my_q - pg_q))
        if missing_q:
            with pg.transaction():
                with pg.cursor() as cur_pg:
                    map_quote = enum_label_mapper(cur_pg, 'quote_estado')
                    for qid in missing_q:
                        with my.cursor() as cur:
                            cur.execute("SELECT * FROM quotes WHERE id=%s", (qid,))
                            qrow = cur.fetchone()
                        if not qrow:
                            continue
                        cur_pg.execute(
                            """
                            INSERT INTO quotes (id, ingreso_id, estado, moneda, subtotal, autorizado_por, forma_pago, fecha_emitido, fecha_aprobado, pdf_url)
                            OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s::quote_estado,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                qrow.get("id"), qrow.get("ingreso_id"), map_quote(qrow.get("estado")) or qrow.get("estado"), qrow.get("moneda"), qrow.get("subtotal"),
                                qrow.get("autorizado_por"), qrow.get("forma_pago"), qrow.get("fecha_emitido"), qrow.get("fecha_aprobado"), qrow.get("pdf_url"),
                            ),
                        )
                        with my.cursor() as cur:
                            cur.execute("SELECT * FROM quote_items WHERE quote_id=%s", (qid,))
                            items = cur.fetchall()
                        map_item = enum_label_mapper(cur_pg, 'quote_item_tipo')
                        for it in items:
                            cur_pg.execute(
                                """
                                INSERT INTO quote_items(id, quote_id, tipo, descripcion, qty, precio_u, repuesto_id)
                                OVERRIDING SYSTEM VALUE
                                VALUES (%s,%s,%s::quote_item_tipo,%s,%s,%s,%s)
                                ON CONFLICT DO NOTHING
                                """,
                                (
                                    it.get("id"), it.get("quote_id"), map_item(it.get("tipo")) or it.get("tipo"), it.get("descripcion"), it.get("qty"), it.get("precio_u"), it.get("repuesto_id"),
                                ),
                            )
            pg.commit()
        # 2.d) events faltantes
        with my.cursor() as cur:
            cur.execute("SELECT id FROM ingreso_events")
            my_e = {int(r["id"]) for r in cur.fetchall()}  # type: ignore[index]
        with pg.cursor() as cur:
            cur.execute("SELECT id FROM ingreso_events")
            pg_e = {int(r[0]) for r in cur.fetchall()}
        missing_e = sorted(list(my_e - pg_e))
        if missing_e:
            with pg.transaction():
                with pg.cursor() as cur_pg:
                    map_ticket = enum_label_mapper(cur_pg, 'ticket_state')
                    for evid in missing_e:
                        with my.cursor() as cur:
                            cur.execute("SELECT * FROM ingreso_events WHERE id=%s", (evid,))
                            ev = cur.fetchone()
                        if not ev:
                            continue
                        cur_pg.execute(
                            """
                            INSERT INTO ingreso_events(id, ticket_id, de_estado, a_estado, usuario_id, ts, comentario)
                            OVERRIDING SYSTEM VALUE
                            VALUES (%s,%s,%s::ticket_state,%s::ticket_state,%s,%s,%s)
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                ev.get("id"), ev.get("ticket_id"), map_ticket(ev.get("de_estado")) or ev.get("de_estado"), map_ticket(ev.get("a_estado")) or ev.get("a_estado"),
                                map_user_by_name(cur_pg, ev.get("usuario_id"), my), ev.get("ts"), ev.get("comentario"),
                            ),
                        )
            pg.commit()
        print("Sincronización delta completa")
    finally:
        try:
            my.close()
        except Exception:
            pass
        try:
            pg.close()
        except Exception:
            pass
