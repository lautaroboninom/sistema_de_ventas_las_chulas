from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Elimina el campo legacy users.perm_ingresar (idempotente)"

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    """
                    DO $$
                    BEGIN
                      IF EXISTS (
                          SELECT 1
                          FROM information_schema.table_constraints
                          WHERE table_name='users'
                            AND constraint_name='users_perm_ingresar_tecnico_chk'
                            AND table_schema = ANY(current_schemas(true))
                      ) THEN
                        ALTER TABLE users DROP CONSTRAINT users_perm_ingresar_tecnico_chk;
                      END IF;
                    END $$;
                    """
                )
                cur.execute(
                    """
                    DO $$
                    BEGIN
                      IF EXISTS (
                          SELECT 1
                          FROM information_schema.columns
                          WHERE table_name='users'
                            AND column_name='perm_ingresar'
                            AND table_schema = ANY(current_schemas(true))
                      ) THEN
                        ALTER TABLE users DROP COLUMN perm_ingresar;
                      END IF;
                    END $$;
                    """
                )

        self.stdout.write("APLICADO OK: eliminado users.perm_ingresar (legacy)")
