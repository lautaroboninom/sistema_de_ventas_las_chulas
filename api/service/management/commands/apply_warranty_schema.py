from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Crea tabla warranty_rules (si no existe) para excepciones de garantía"

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS warranty_rules (
                      id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                      brand_id      INTEGER NULL REFERENCES marcas(id) ON DELETE SET NULL,
                      model_id      INTEGER NULL REFERENCES models(id) ON DELETE SET NULL,
                      serial_prefix TEXT,
                      days          INTEGER NOT NULL,
                      notas         TEXT,
                      activo        BOOLEAN NOT NULL DEFAULT TRUE,
                      created_by    INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                      created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_by    INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                      updated_at    TIMESTAMPTZ NULL
                    );
                    """
                )
                # Índices simples
                cur.execute("CREATE INDEX IF NOT EXISTS idx_wr_brand ON warranty_rules(brand_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_wr_model ON warranty_rules(model_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_wr_activo ON warranty_rules(activo)")
        self.stdout.write("APLICADO OK: warranty_rules (schema)")

