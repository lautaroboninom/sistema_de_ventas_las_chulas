from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Ejecuta Paso 1: Backfill devices.numero_interno desde n_de_control y recalcula snapshot devices.n_de_control desde ingresos.faja_garantia (último ingreso)"

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                self.stdout.write("[1/3] Asegurar columna devices.numero_interno")
                cur.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS numero_interno TEXT")

                self.stdout.write("[2/3] Backfill numero_interno desde n_de_control donde esté vacío/nulo (evita duplicados)")
                cur.execute(
                    """
                    WITH cand AS (
                      SELECT d.id,
                             UPPER(REGEXP_REPLACE(NULLIF(d.n_de_control,''),
                               '^(MG|NM|NV|CE)\s*(\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0'))) AS norm
                        FROM devices d
                       WHERE (d.numero_interno IS NULL OR d.numero_interno = '')
                         AND NULLIF(d.n_de_control,'') IS NOT NULL
                    )
                    UPDATE devices d
                       SET numero_interno = c.norm
                      FROM cand c
                     WHERE d.id = c.id
                       AND c.norm IS NOT NULL
                       AND NOT EXISTS (
                         SELECT 1
                           FROM devices x
                          WHERE x.id <> d.id
                            AND UPPER(REGEXP_REPLACE(x.numero_interno,
                                '^(MG|NM|NV|CE)\s*(\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0'))) = c.norm
                       )
                    """
                )
                self.stdout.write(f"  filas actualizadas: {cur.rowcount}")

                self.stdout.write("[3/3] Recalcular snapshot n_de_control desde último ingresos.faja_garantia")
                cur.execute(
                    """
                    WITH last_ingreso AS (
                      SELECT DISTINCT ON (t.device_id)
                             t.device_id,
                             NULLIF(t.faja_garantia,'') AS faja
                        FROM ingresos t
                       ORDER BY t.device_id, COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
                    )
                    UPDATE devices d
                       SET n_de_control = COALESCE(li.faja, d.n_de_control)
                      FROM last_ingreso li
                     WHERE d.id = li.device_id
                    """
                )
                self.stdout.write(f"  filas snapshot: {cur.rowcount}")
        self.stdout.write("OK: Paso 1 ejecutado")
