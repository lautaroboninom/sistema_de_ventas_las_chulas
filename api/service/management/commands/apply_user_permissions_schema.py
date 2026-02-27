from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Crea/asegura schema para overrides de permisos por usuario"

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_permission_overrides (
                      id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                      user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                      permission_code  TEXT    NOT NULL,
                      effect           TEXT    NOT NULL,
                      updated_by       INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                      created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      CONSTRAINT uq_user_permission_overrides UNIQUE (user_id, permission_code),
                      CONSTRAINT chk_user_permission_effect CHECK (effect IN ('allow','deny'))
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_permission_overrides_user_id
                    ON user_permission_overrides(user_id)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_permission_overrides_permission_code
                    ON user_permission_overrides(permission_code)
                    """
                )
                cur.execute(
                    """
                    CREATE OR REPLACE FUNCTION trg_set_updated_at_user_permission_overrides()
                    RETURNS TRIGGER AS $$
                    BEGIN
                      NEW.updated_at := NOW();
                      RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                    """
                )
                cur.execute(
                    """
                    DROP TRIGGER IF EXISTS set_updated_at_user_permission_overrides
                    ON user_permission_overrides
                    """
                )
                cur.execute(
                    """
                    CREATE TRIGGER set_updated_at_user_permission_overrides
                    BEFORE UPDATE ON user_permission_overrides
                    FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at_user_permission_overrides()
                    """
                )

        self.stdout.write("APLICADO OK: user_permission_overrides (schema)")

