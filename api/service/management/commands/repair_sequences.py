from django.core.management.base import BaseCommand
from django.db import connection


ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_ .")


def _safe_ident(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    low = s.lower()
    if any(ch not in ALLOWED_CHARS for ch in low):
        return None
    # normalize: collapse spaces
    return " ".join(low.split())


def _qualify(schema: str | None, table: str) -> str:
    if schema:
        return f"{schema}.{table}"
    return table


def _detect_tables(schema: str | None = None) -> list[tuple[str | None, str]]:
    if connection.vendor != "postgresql":
        return []
    where_schema = ""
    params = []
    if schema:
        where_schema = "AND c.table_schema = %s"
        params.append(schema)
    sql = f"""
        SELECT c.table_schema, c.table_name
          FROM information_schema.columns c
         WHERE c.column_name = 'id'
           AND (c.is_identity = 'YES' OR c.column_default LIKE 'nextval%%')
           {where_schema}
         ORDER BY c.table_schema, c.table_name
    """
    with connection.cursor() as cur:
        cur.execute(sql, params)
        return [(r[0], r[1]) for r in cur.fetchall()]


def _repair_table(schema: str | None, table: str, dry_run: bool = False) -> tuple[bool, str]:
    if connection.vendor != "postgresql":
        return False, "No PostgreSQL vendor"
    s_schema = _safe_ident(schema) if schema else None
    s_table = _safe_ident(table)
    if not s_table:
        return False, f"Invalid identifier: {schema}.{table if table else ''}"
    qualified = _qualify(s_schema, s_table)
    sql = (
        f"SELECT setval(pg_get_serial_sequence(%s, 'id'), "
        f"COALESCE((SELECT MAX(id) FROM {qualified}), 1))"
    )
    if dry_run:
        return True, f"DRY-RUN would run: {sql} [table={qualified}]"
    try:
        with connection.cursor() as cur:
            cur.execute(sql, [qualified])
        return True, f"OK: repaired sequence for {qualified}"
    except Exception as e:
        try:
            connection.rollback()
        except Exception:
            pass
        return False, f"ERR {qualified}: {e}"


class Command(BaseCommand):
    help = "Realinea las secuencias de PK (id) a MAX(id) para tablas dadas o detectadas. Solo PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tables",
            action="append",
            default=[],
            help=(
                "Lista de tablas (coma-separadas) opcional. "
                "Si no se especifica, se detectan automáticamente. "
                "Ejemplo: --tables devices,ingresos,users"
            ),
        )
        parser.add_argument(
            "--schema",
            default="public",
            help="Esquema a usar (default: public).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra lo que se haría sin ejecutar cambios.",
        )

    def handle(self, *args, **opts):
        if connection.vendor != "postgresql":
            self.stderr.write("Solo soportado en PostgreSQL.")
            return 1

        schema = (opts.get("schema") or "public").strip() or None
        dry = bool(opts.get("dry_run"))

        tables_arg = opts.get("tables") or []
        table_list = []
        for it in tables_arg:
            if not it:
                continue
            for t in str(it).split(","):
                t = (t or "").strip()
                if t:
                    table_list.append((schema, t))

        if not table_list:
            detected = _detect_tables(schema)
            if not detected:
                self.stdout.write("No se detectaron tablas con secuencia de id.")
                return 0
            table_list = detected

        ok_all = True
        for s, t in table_list:
            ok, msg = _repair_table(s, t, dry_run=dry)
            (self.stdout.write if ok else self.stderr.write)(msg)
            ok_all = ok_all and ok

        return 0 if ok_all else 2
