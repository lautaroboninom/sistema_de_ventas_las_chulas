from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Crea/actualiza tabla ingreso_tests para protocolo de test tecnico y trazabilidad de referencias."

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                if connection.vendor == "postgresql":
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS ingreso_tests (
                          id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                          ingreso_id           INTEGER NOT NULL REFERENCES ingresos(id) ON DELETE CASCADE,
                          template_key         TEXT NOT NULL,
                          template_version     TEXT NOT NULL,
                          tipo_equipo_snapshot TEXT,
                          payload              JSONB NOT NULL DEFAULT '{}'::jsonb,
                          references_snapshot  JSONB NOT NULL DEFAULT '[]'::jsonb,
                          resultado_global     TEXT NOT NULL DEFAULT 'pendiente',
                          conclusion           TEXT,
                          instrumentos         TEXT,
                          firmado_por          TEXT,
                          fecha_ejecucion      TIMESTAMPTZ NULL,
                          tecnico_id           INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                          created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                          updated_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                else:
                    # SQLite fallback for local tests/dev.
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS ingreso_tests (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          ingreso_id INTEGER NOT NULL UNIQUE,
                          template_key TEXT NOT NULL,
                          template_version TEXT NOT NULL,
                          tipo_equipo_snapshot TEXT,
                          payload TEXT NOT NULL DEFAULT '{}',
                          references_snapshot TEXT NOT NULL DEFAULT '[]',
                          resultado_global TEXT NOT NULL DEFAULT 'pendiente',
                          conclusion TEXT,
                          instrumentos TEXT,
                          firmado_por TEXT,
                          fecha_ejecucion DATETIME NULL,
                          tecnico_id INTEGER NULL,
                          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )

                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_ingreso_tests_ingreso ON ingreso_tests(ingreso_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS ix_ingreso_tests_template_key ON ingreso_tests(template_key)")
                cur.execute("CREATE INDEX IF NOT EXISTS ix_ingreso_tests_updated_at ON ingreso_tests(updated_at)")

        self.stdout.write("APLICADO OK: esquema ingreso_tests")

