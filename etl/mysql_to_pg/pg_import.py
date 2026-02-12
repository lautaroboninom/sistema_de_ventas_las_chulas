import os
import csv
import sys
import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb
import re
import unicodedata


def env(name, default=None):
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


def insert_rows(conn, table: str, columns: list[str], rows):
    id_in_cols = 'id' in columns
    cols_sql = ', '.join(columns)
    def _ph(col: str) -> str:
        # Tipado explícito en PostgreSQL para columnas ENUM
        if table == 'ingresos':
            if col == 'motivo':
                return "%s::motivo_ingreso"
            if col == 'estado':
                return "%s::ticket_state"
            if col == 'disposicion':
                return "%s::disposicion_type"
            if col == 'presupuesto_estado':
                return "%s::quote_estado"
        if table == 'quotes' and col == 'estado':
            return "%s::quote_estado"
        if table == 'ingreso_events' and col in ('a_estado','de_estado'):
            return "%s::ticket_state"
        return "%s"
    placeholders = ', '.join([_ph(c) for c in columns])
    overriding = ' OVERRIDING SYSTEM VALUE' if id_in_cols else ''
    conflict = " ON CONFLICT (id) DO NOTHING" if id_in_cols else ""
    sql = f"INSERT INTO {table} ({cols_sql}){overriding} VALUES ({placeholders}){conflict}"
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
        if id_in_cols:
            # Sincronizar secuencia del identity con el max(id)
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table):
                raise ValueError(f"Invalid table name: {table}")
            seq_sql = (
                f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
                f"(SELECT COALESCE(MAX(id),0) FROM {table}), true);"
            )
            cur.execute(seq_sql)


def adapt_row(table: str, cols: list[str], rowdict: dict):
    # Mapas de campos booleanos por tabla
    BOOL_FIELDS = {
        'users': {'activo', 'perm_ingresar'},
        'ingresos': {'garantia_reparacion', 'alquilado'},
        'devices': {'garantia_bool', 'etiq_garantia_ok', 'alquilado'},
        'handoffs': {'firmado_cliente', 'firmado_empresa', 'remito_impreso'},
        'catalogo_accesorios': {'activo'},
        'catalogo_tipos_equipo': {'activo'},
        'marca_tipos_equipo': {'activo'},
        'marca_series': {'activo'},
        'marca_series_variantes': {'activo'},
    }

    def _to_bool(v):
        if v is None or v == '':
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return bool(v)
        s = str(v).strip().lower()
        if s in ('1', 't', 'true', 'yes', 'y'): return True
        if s in ('0', 'f', 'false', 'no', 'n'): return False
        # fallback: intentar int
        try:
            return bool(int(s))
        except Exception:
            return None

    def _strip(s):
        return s.strip() if isinstance(s, str) else s

    def _fix_mojibake(s: str) -> str:
        if not isinstance(s, str):
            return s
        try:
            if any(ch in s for ch in ("�", "ǟ", "ǽ")):
                return s.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
        except Exception:
            pass
        return s

    def _simp(s: str) -> str:
        if not isinstance(s, str):
            return s
        s = _strip(_fix_mojibake(s)).lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = ' '.join(s.split())
        return s

    def _normalize_enum(col: str, val):
        if not isinstance(val, str):
            return val
        key = _simp(val)
        if table == 'ingresos':
            if col == 'motivo':
                mapa = {
                    'reparacion': 'reparación',
                    'service preventivo': 'service preventivo',
                    'baja alquiler': 'baja alquiler',
                    'reparacion alquiler': 'reparación alquiler',
                    'urgente control': 'urgente control',
                    'devolucion demo': 'devolución demo',
                    'otros': 'otros',
                }
                return mapa.get(key, 'otros')
            if col == 'estado':
                mapa = {k: k for k in (
                    'ingresado','diagnosticado','presupuestado','reparar','reparado','entregado','baja','derivado','liberado','alquilado'
                )}
                return mapa.get(key, 'ingresado')
            if col == 'disposicion':
                mapa = {'normal': 'normal', 'para repuesto': 'para_repuesto', 'para_repuesto': 'para_repuesto'}
                return mapa.get(key, 'normal')
            if col == 'presupuesto_estado':
                mapa = {k: k for k in ('pendiente','emitido','aprobado','rechazado','presupuestado')}
                return mapa.get(key, 'pendiente')
        if table == 'quotes':
            if col == 'estado':
                # PG best-practice: valores cerrados. Mapear legacy MySQL -> PG
                mapa = {
                    'pendiente': 'pendiente',
                    'emitido': 'emitido',
                    'enviado': 'presupuestado',  # legacy: tratar "enviado" como presupuestado
                    'presupuestado': 'presupuestado',
                    'aprobado': 'aprobado',
                    'rechazado': 'rechazado',
                }
                return mapa.get(key, 'pendiente')
        if table == 'ingreso_events':
            if col in ('a_estado','de_estado'):
                mapa = {k: k for k in (
                    'ingresado','diagnosticado','presupuestado','reparar','reparado','entregado','baja','derivado','liberado','alquilado'
                )}
                return mapa.get(key, None)
        return val

    out = []
    bools = BOOL_FIELDS.get(table, set())
    for c in cols:
        val = rowdict.get(c)
        if isinstance(val, str) and val == "":
            val = None
        if table == 'ingresos' and c in ('motivo','estado','disposicion','presupuesto_estado') and val is not None:
            val = _normalize_enum(c, val)
        if c in bools:
            val = _to_bool(val)
        if table == 'audit_log' and c == 'body' and val not in (None, ''):
            try:
                obj = val if isinstance(val, (dict, list)) else json.loads(val)
                val = Jsonb(obj)
            except Exception:
                # dejar como texto; PG intentará castear si es válido
                pass
        out.append(val)
    return out


SKIP_COLUMNS = {
    # columnas generadas en PG (no se pueden insertar)
    'quotes': {'iva_21', 'total'},
    'ingreso_events': {'ingreso_id'},
    'model_hierarchy': {'variant_key'},
}


def main():
    if len(sys.argv) < 2:
        print("Uso: pg_import.py <directorio_backup>")
        sys.exit(1)
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"No existe: {src}")
        sys.exit(1)

    conn = connect_pg()
    conn.execute("SET TIME ZONE 'UTC'")
    try:
        with conn.transaction():
            files = list(src.glob('*.csv'))
            order = {
                'users': 1,
                'marcas': 2,
                'models': 3,
                'locations': 4,
                'customers': 5,
                'proveedores_externos': 6,
                'catalogo_tipos_equipo': 7,
                'catalogo_accesorios': 7,
                'marca_tipos_equipo': 8,
                'marca_series': 9,
                'marca_series_variantes': 10,
                'model_hierarchy': 11,
                'devices': 12,
                'password_reset_tokens': 90,
                'ingresos': 20,
                'quotes': 21,
                'quote_items': 22,
                'ingreso_media': 31,
                'ingreso_events': 32,
                'ingreso_accesorios': 33,
                'handoffs': 34,
                'equipos_derivados': 35,
            }
            files.sort(key=lambda p: order.get(p.stem, 100))
            CLEAR_TABLES = {'locations'}
            for csv_path in files:
                table = csv_path.stem
                # 'audit_log' es opcional; se puede omitir si no se requiere
                # if table == 'audit_log':
                #     continue
                with csv_path.open('r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    cols = reader.fieldnames or []
                    skip = SKIP_COLUMNS.get(table, set())
                    cols = [c for c in cols if c not in skip]
                    batch = []
                    for row in reader:
                        batch.append(adapt_row(table, cols, row))
                    if batch:
                        if table in CLEAR_TABLES:
                            conn.execute(f"DELETE FROM {table}")

                        # Normalizaciones por tabla con FKs potencialmente rotas o faltantes en origen
                        if table == 'devices':
                            # Validacion y saneo de FKs de devices -> customers/marcas/models
                            with conn.cursor() as cur:
                                cur.execute("SELECT id FROM customers")
                                valid_customers = {r[0] for r in cur.fetchall()}
                                cur.execute("SELECT id FROM marcas")
                                valid_marcas = {r[0] for r in cur.fetchall()}
                                cur.execute("SELECT id FROM models")
                                valid_models = {r[0] for r in cur.fetchall()}
                                fallback_cid = None
                                if not valid_customers:
                                    cur.execute("INSERT INTO customers(razon_social) VALUES ('MIGRACION') RETURNING id")
                                    fallback_cid = cur.fetchone()[0]
                                    valid_customers.add(fallback_cid)
                                else:
                                    fallback_cid = next(iter(valid_customers))
                            i_c = cols.index('customer_id') if 'customer_id' in cols else -1
                            i_marca = cols.index('marca_id') if 'marca_id' in cols else -1
                            i_model = cols.index('model_id') if 'model_id' in cols else -1
                            fixed = []
                            for row in batch:
                                row = list(row)
                                if i_c >= 0 and (row[i_c] is None or row[i_c] not in valid_customers):
                                    row[i_c] = fallback_cid
                                if i_marca >= 0 and (row[i_marca] is not None) and (row[i_marca] not in valid_marcas):
                                    row[i_marca] = None
                                if i_model >= 0 and (row[i_model] is not None) and (row[i_model] not in valid_models):
                                    row[i_model] = None
                                fixed.append(row)
                            batch = fixed

                        if table == 'ingresos':
                            # Asegurar que existan los devices referenciados; crear stubs si faltan
                            idx_dev = cols.index('device_id') if 'device_id' in cols else -1
                            if idx_dev >= 0:
                                dev_ids = {r[idx_dev] for r in batch if r[idx_dev] is not None}
                                with conn.cursor() as cur:
                                    existing = set()
                                    if dev_ids:
                                        cur.execute("SELECT id FROM devices WHERE id = ANY(%s)", (list(dev_ids),))
                                        existing = {r[0] for r in cur.fetchall()}
                                    missing = [d for d in dev_ids if d not in existing]
                                    if missing:
                                        # asegurar customer fallback
                                        cur.execute("SELECT id FROM customers")
                                        custs = {r[0] for r in cur.fetchall()}
                                        if not custs:
                                            cur.execute("INSERT INTO customers(razon_social) VALUES ('MIGRACION') RETURNING id")
                                            fallback_cid = cur.fetchone()[0]
                                        else:
                                            fallback_cid = next(iter(custs))
                                        stub_rows = [[mid, fallback_cid] for mid in missing]
                                        insert_rows(conn, 'devices', ['id','customer_id'], stub_rows)
                                # Limpiar FKs a users/locations si faltan
                                with conn.cursor() as cur:
                                    cur.execute("SELECT id FROM users")
                                    user_ids = {r[0] for r in cur.fetchall()}
                                    cur.execute("SELECT id FROM locations")
                                    loc_ids = {r[0] for r in cur.fetchall()}
                                i_rec = cols.index('recibido_por') if 'recibido_por' in cols else -1
                                i_asg = cols.index('asignado_a') if 'asignado_a' in cols else -1
                                i_loc = cols.index('ubicacion_id') if 'ubicacion_id' in cols else -1
                                fixed = []
                                for row in batch:
                                    row = list(row)
                                    if i_rec >= 0 and row[i_rec] is not None and row[i_rec] not in user_ids:
                                        row[i_rec] = None
                                    if i_asg >= 0 and row[i_asg] is not None and row[i_asg] not in user_ids:
                                        row[i_asg] = None
                                    if i_loc >= 0 and row[i_loc] is not None and row[i_loc] not in loc_ids:
                                        row[i_loc] = None
                                    fixed.append(row)
                                batch = fixed

                        if table == 'ingreso_media':
                            # usuario_id es NOT NULL: forzar a usuario MIGRACION si no existen usuarios
                            i_uid = cols.index('usuario_id') if 'usuario_id' in cols else -1
                            if i_uid >= 0:
                                with conn.cursor() as cur:
                                    cur.execute("SELECT id FROM users")
                                    users = {r[0] for r in cur.fetchall()}
                                    if not users:
                                        cur.execute(
                                            "INSERT INTO users(nombre, email, rol, activo, perm_ingresar) VALUES (%s,%s,%s,TRUE,FALSE) RETURNING id",
                                            ('MIGRACION', 'migracion@local.invalid', 'tecnico')
                                        )
                                        mig_uid = cur.fetchone()[0]
                                    else:
                                        mig_uid = next(iter(users))
                                fixed = []
                                for row in batch:
                                    row = list(row)
                                    row[i_uid] = mig_uid
                                    fixed.append(row)
                                batch = fixed

                        if table == 'ingreso_events':
                            # usuario_id puede ser NULL: si no existe en users, limpiar
                            i_uid = cols.index('usuario_id') if 'usuario_id' in cols else -1
                            if i_uid >= 0:
                                with conn.cursor() as cur:
                                    cur.execute("SELECT id FROM users")
                                    user_ids = {r[0] for r in cur.fetchall()}
                                fixed = []
                                for row in batch:
                                    row = list(row)
                                    if row[i_uid] is not None and row[i_uid] not in user_ids:
                                        row[i_uid] = None
                                    fixed.append(row)
                                batch = fixed

                        if table == 'ingreso_accesorios':
                            # Asegurar existencia de catalogo de accesorios referenciados
                            i_acc = cols.index('accesorio_id') if 'accesorio_id' in cols else -1
                            if i_acc >= 0:
                                acc_ids = {r[i_acc] for r in batch if r[i_acc] is not None}
                                with conn.cursor() as cur:
                                    existing = set()
                                    if acc_ids:
                                        cur.execute("SELECT id FROM catalogo_accesorios WHERE id = ANY(%s)", (list(acc_ids),))
                                        existing = {r[0] for r in cur.fetchall()}
                                    missing = [a for a in acc_ids if a not in existing]
                                if missing:
                                    rows_acc = [[aid, f'ACC_{aid}', True] for aid in missing]
                                    insert_rows(conn, 'catalogo_accesorios', ['id','nombre','activo'], rows_acc)

                        if table == 'equipos_derivados':
                            # Asegurar existencia de proveedores externos referenciados
                            i_prov = cols.index('proveedor_id') if 'proveedor_id' in cols else -1
                            if i_prov >= 0:
                                prov_ids = {r[i_prov] for r in batch if r[i_prov] is not None}
                                with conn.cursor() as cur:
                                    existing = set()
                                    if prov_ids:
                                        cur.execute("SELECT id FROM proveedores_externos WHERE id = ANY(%s)", (list(prov_ids),))
                                        existing = {r[0] for r in cur.fetchall()}
                                    missing = [p for p in prov_ids if p not in existing]
                                if missing:
                                    rows_prov = [[pid, f'PROV_{pid}'] for pid in missing]
                                    insert_rows(conn, 'proveedores_externos', ['id','nombre'], rows_prov)

                        insert_rows(conn, table, cols, batch)
                        print(f"Importadas {len(batch)} filas en {table}")
        # commit explícito por claridad
        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
