from django.core.management.base import BaseCommand
from django.db import connection, transaction
import os


class Command(BaseCommand):
    help = (
        "Ajusta ubicaciones de ingresos: alquilados → '-' ; 'Sarmiento' → 'Taller' (no alquilados)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra cambios sin aplicar (default)")
        parser.add_argument("--apply", action="store_true", help="Aplica cambios en BD")

    def _ensure_location(self, cur, name: str) -> int:
        cur.execute("SELECT id FROM locations WHERE LOWER(nombre)=LOWER(%s) LIMIT 1", [name])
        r = cur.fetchone()
        if r:
            return int(r[0])
        cur.execute("INSERT INTO locations(nombre) VALUES (%s) RETURNING id", [name])
        return int(cur.fetchone()[0])

    def handle(self, *args, **opts):
        dry = True
        if opts.get("apply"):
            dry = False
        if opts.get("dry_run"):
            dry = True

        with transaction.atomic():
            with connection.cursor() as cur:
                # IDs canónicos necesarios
                taller_id = self._ensure_location(cur, "Taller")
                dash_loc_id = self._ensure_location(cur, "-")

                # Conteos previos
                cur.execute(
                    """
                    SELECT COUNT(*)
                      FROM ingresos t
                      LEFT JOIN locations l ON l.id = t.ubicacion_id
                     WHERE COALESCE(t.alquilado,false)=true
                       AND (l.id IS DISTINCT FROM %s)
                    """,
                    [dash_loc_id],
                )
                to_alquilado = int(cur.fetchone()[0] or 0)

                cur.execute(
                    """
                    SELECT COUNT(*)
                      FROM ingresos t
                      JOIN locations l ON l.id = t.ubicacion_id
                     WHERE LOWER(l.nombre) = LOWER(%s)
                       AND COALESCE(t.alquilado,false) = false
                    """,
                    ["Sarmiento"],
                )
                to_taller = int(cur.fetchone()[0] or 0)

                # Aplicación
                if not dry:
                    # 1) Alquilados → '-'
                    cur.execute(
                        """
                        UPDATE ingresos SET ubicacion_id = %s
                         WHERE id IN (
                           SELECT t.id
                             FROM ingresos t
                             LEFT JOIN locations l ON l.id = t.ubicacion_id
                            WHERE COALESCE(t.alquilado,false)=true
                              AND (l.id IS DISTINCT FROM %s)
                         )
                        """,
                        [dash_loc_id, dash_loc_id],
                    )

                    # 2) 'Sarmiento' (no alquilados) → 'Taller'
                    cur.execute(
                        """
                        UPDATE ingresos SET ubicacion_id = %s
                         WHERE id IN (
                           SELECT t.id
                             FROM ingresos t
                             JOIN locations l ON l.id = t.ubicacion_id
                            WHERE LOWER(l.nombre) = LOWER(%s)
                              AND COALESCE(t.alquilado,false) = false
                         )
                        """,
                        [taller_id, "Sarmiento"],
                    )

                # Si es dry-run, revertir
                if dry:
                    transaction.set_rollback(True)

        self.stdout.write(
            ("DRY-RUN " if dry else "APLICADO ") +
            f"OK. Ingresos -> 'Alquilado': {to_alquilado} | 'Sarmiento'->'Taller': {to_taller}"
        )
