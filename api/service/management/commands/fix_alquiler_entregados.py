from django.core.management.base import BaseCommand
from django.db import connection, transaction

from service.constants import DEFAULT_LOCATION_NAMES
from service.views.helpers_impl import ensure_default_locations


class Command(BaseCommand):
    help = (
        "Corrige ingresos en 'Estanteria de Alquiler' con estado entregado. "
        "Los marca como alquilado y mueve la ubicacion a '-'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra cambios sin aplicar (default)",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica cambios en BD",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limita la cantidad de ingresos a corregir (por id desc)",
        )
        parser.add_argument(
            "--show-ids",
            type=int,
            default=20,
            help="Cantidad maxima de IDs a mostrar",
        )

    def _ensure_location(self, cur, name: str) -> int:
        cur.execute(
            "SELECT id FROM locations WHERE LOWER(nombre)=LOWER(%s) ORDER BY id LIMIT 1",
            [name],
        )
        row = cur.fetchone()
        if row:
            return int(row[0])
        cur.execute("INSERT INTO locations(nombre) VALUES (%s) RETURNING id", [name])
        return int(cur.fetchone()[0])

    def _get_location_ids(self, cur, name: str):
        cur.execute("SELECT id FROM locations WHERE LOWER(nombre)=LOWER(%s)", [name])
        ids = [int(r[0]) for r in (cur.fetchall() or [])]
        if not ids:
            ids = [self._ensure_location(cur, name)]
        return ids

    def _pick_estanteria_name(self) -> str:
        for name in (DEFAULT_LOCATION_NAMES or []):
            if "Estanter" in str(name):
                return str(name)
        return "Estanteria de Alquiler"

    def handle(self, *args, **opts):
        dry = True
        if opts.get("apply"):
            dry = False
        if opts.get("dry_run"):
            dry = True

        limit = opts.get("limit")
        show_ids = opts.get("show_ids") or 0

        with transaction.atomic():
            with connection.cursor() as cur:
                try:
                    ensure_default_locations()
                except Exception:
                    # No bloquear por problemas de normalizacion de ubicaciones
                    pass

                estanteria_name = self._pick_estanteria_name()
                estanteria_ids = self._get_location_ids(cur, estanteria_name)
                dash_id = self._ensure_location(cur, "-")

                if not estanteria_ids:
                    self.stdout.write("No se encontro ubicacion de Estanteria de Alquiler.")
                    if dry:
                        transaction.set_rollback(True)
                    return

                placeholders = ",".join(["%s"] * len(estanteria_ids))
                limit_sql = ""
                if limit is not None and int(limit) > 0:
                    limit_sql = " LIMIT %s"

                params = list(estanteria_ids)
                if limit_sql:
                    params.append(int(limit))

                cur.execute(
                    f"""
                    SELECT t.id
                      FROM ingresos t
                     WHERE t.ubicacion_id IN ({placeholders})
                       AND LOWER(TRIM(COALESCE(t.estado::text,''))) = 'entregado'
                     ORDER BY t.id DESC
                     {limit_sql}
                    """,
                    params,
                )
                ids = [int(r[0]) for r in (cur.fetchall() or [])]

                if ids:
                    cur.execute(
                        """
                        UPDATE ingresos
                           SET estado='alquilado',
                               alquilado=true,
                               ubicacion_id=%s
                         WHERE id = ANY(%s)
                        """,
                        [dash_id, ids],
                    )

                if dry:
                    transaction.set_rollback(True)

        msg = ("DRY-RUN " if dry else "APLICADO ") + f"OK. corregidos={len(ids)}"
        if show_ids and ids:
            sample = ", ".join(str(i) for i in ids[: int(show_ids)])
            msg += f" | ids: {sample}"
        self.stdout.write(msg)
