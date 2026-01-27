from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Crea tabla ingreso_presupuesto_alerts para avisos de presupuestos pendientes"

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ingreso_presupuesto_alerts (
                      id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                      ingreso_id   INTEGER NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
                      last_sent_at TIMESTAMPTZ NULL,
                      created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_ingreso_presupuesto_alerts_ingreso ON ingreso_presupuesto_alerts(ingreso_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS ix_ingreso_presupuesto_alerts_last_sent ON ingreso_presupuesto_alerts(last_sent_at)"
                )
                if connection.vendor == "postgresql":
                    cur.execute(
                        """
                        DO $$ BEGIN
                          IF NOT EXISTS (
                            SELECT 1 FROM pg_trigger WHERE tgname='trg_ingreso_presupuesto_alerts_set_updated_at'
                          ) THEN
                            CREATE TRIGGER trg_ingreso_presupuesto_alerts_set_updated_at
                            BEFORE UPDATE ON ingreso_presupuesto_alerts
                            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
                          END IF;
                        END $$;
                        """
                    )
        self.stdout.write("APLICADO OK: ingreso_presupuesto_alerts (schema)")
