import os
import sys


def main():
    # Ensure we can import Django settings from api/app
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, os.pardir))
    api_dir = os.path.join(repo, "api")
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

    import django
    django.setup()

    from django.db import connection

    with connection.cursor() as cur:
        # Check column existence (schema-aware)
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
             WHERE table_name = 'ingresos'
               AND column_name = 'empresa_facturar'
               AND table_schema = ANY(current_schemas(true))
             LIMIT 1
            """
        )
        has_col = cur.fetchone() is not None
        if not has_col:
            print("Adding column ingresos.empresa_facturar ...")
            cur.execute("ALTER TABLE ingresos ADD COLUMN empresa_facturar TEXT NOT NULL DEFAULT 'SEPID'")
        else:
            print("Column ingresos.empresa_facturar already exists")

        # Check constraint existence
        cur.execute(
            """
            SELECT 1
              FROM information_schema.table_constraints tc
             WHERE tc.table_name='ingresos'
               AND tc.constraint_type='CHECK'
               AND tc.constraint_name='ingresos_empresa_facturar_chk'
               AND tc.table_schema = ANY(current_schemas(true))
             LIMIT 1
            """
        )
        has_chk = cur.fetchone() is not None
        if not has_chk:
            print("Adding CHECK constraint ingresos_empresa_facturar_chk ...")
            cur.execute(
                "ALTER TABLE ingresos ADD CONSTRAINT ingresos_empresa_facturar_chk CHECK (empresa_facturar IN ('SEPID','MGBIO'))"
            )
        else:
            print("Constraint ingresos_empresa_facturar_chk already exists")

    print("Done.")


if __name__ == "__main__":
    main()

