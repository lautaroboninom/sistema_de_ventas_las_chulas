from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = (
        "Aplica cambios de esquema (Fase 2): devices: +numero_interno,+tipo_equipo,+variante,+garantia_vence; "
        "+ingresos.etiq_garantia_ok; backfill basico; drop devices.etiq_garantia_ok y garantia_bool."
    )

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                # 1) Add new columns to devices (if not exists)
                cur.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS numero_interno TEXT")
                cur.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS tipo_equipo TEXT")
                cur.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS variante TEXT")
                cur.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS garantia_vence DATE")

                # 2) Add etiq_garantia_ok to ingresos
                cur.execute("ALTER TABLE ingresos ADD COLUMN IF NOT EXISTS etiq_garantia_ok BOOLEAN")

                # 3) Backfill etiq_garantia_ok from devices -> último ingreso de cada device
                # Solo si la columna existe en devices
                cur.execute(
                    "SELECT 1 FROM information_schema.columns WHERE table_name='devices' AND column_name='etiq_garantia_ok'"
                )
                if cur.fetchone():
                    cur.execute(
                        """
                        WITH last_ingreso AS (
                          SELECT d.id AS device_id,
                                 (
                                   SELECT t.id FROM ingresos t
                                    WHERE t.device_id = d.id
                                    ORDER BY COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
                                    LIMIT 1
                                 ) AS ingreso_id
                            FROM devices d
                        )
                        UPDATE ingresos t
                           SET etiq_garantia_ok = d.etiq_garantia_ok
                          FROM devices d
                          JOIN last_ingreso li ON li.device_id = d.id
                         WHERE t.id = li.ingreso_id
                           AND d.etiq_garantia_ok IS NOT NULL
                           AND (t.etiq_garantia_ok IS DISTINCT FROM d.etiq_garantia_ok)
                        """
                    )

                # 4) Backfill numero_interno desde numero_serie si parece código interno
                cur.execute(
                    """
                    UPDATE devices d
                       SET numero_interno = UPPER(REGEXP_REPLACE(d.numero_serie, '^(MG|NM|NV|CE)\s*(\d{1,4})$', '\1 ' || LPAD('\2',4,'0')))
                     WHERE d.numero_serie ~* '^(MG|NM|NV|CE)\s*\d{1,4}$'
                       AND (d.numero_interno IS NULL OR d.numero_interno = '')
                    """
                )

                # 5) Backfill tipo_equipo/variante desde models
                cur.execute(
                    """
                    UPDATE devices d
                       SET tipo_equipo = COALESCE(d.tipo_equipo, m.tipo_equipo),
                           variante    = COALESCE(d.variante, m.variante)
                      FROM models m
                     WHERE m.id = d.model_id
                       AND (d.tipo_equipo IS NULL OR d.variante IS NULL)
                    """
                )

                # 6) Drop columns moved/removed from devices (if exist)
                for col in ("etiq_garantia_ok", "garantia_bool"):
                    cur.execute(
                        "SELECT 1 FROM information_schema.columns WHERE table_name='devices' AND column_name=%s",
                        [col],
                    )
                    if cur.fetchone():
                        cur.execute(f"ALTER TABLE devices DROP COLUMN {col}")

        self.stdout.write("APLICADO OK: Fase 2 (schema y backfill básico)")

