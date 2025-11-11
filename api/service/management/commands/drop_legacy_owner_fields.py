from django.core.management.base import BaseCommand
from django.db import connection, transaction


DDL_FUNC_NO_OWNER = r"""
CREATE OR REPLACE FUNCTION sync_device_snapshot()
RETURNS TRIGGER AS $$
DECLARE
  v_device_id INTEGER;
  v_last_id INTEGER;
  v_alquilado BOOLEAN;
  v_alquiler_a TEXT;
  v_faja TEXT;
  v_ubic_id INTEGER;
BEGIN
  v_device_id := COALESCE(NEW.device_id, OLD.device_id);

  -- ultimo ingreso del equipo afectado
  SELECT t.id, t.alquilado, t.alquiler_a,
         t.faja_garantia, t.ubicacion_id
    INTO v_last_id, v_alquilado, v_alquiler_a,
         v_faja, v_ubic_id
    FROM ingresos t
   WHERE t.device_id = v_device_id
   ORDER BY COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
   LIMIT 1;

  -- Actualizar snapshot en devices (sin propietario desde ingresos)
  UPDATE devices d
     SET alquilado = COALESCE(v_alquilado, FALSE),
         alquiler_a = v_alquiler_a,
         ubicacion_id = COALESCE(v_ubic_id, d.ubicacion_id),
         n_de_control = COALESCE(NULLIF(v_faja, ''), d.n_de_control)
   WHERE d.id = v_device_id;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


class Command(BaseCommand):
    help = "Fase 2: deja de depender de ingresos.propietario_* y elimina columnas legacy"

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                # 1) Reemplazar funcion + triggers de snapshot para no referenciar propietario_* de ingresos
                cur.execute(DDL_FUNC_NO_OWNER)
                cur.execute("DROP TRIGGER IF EXISTS trg_sync_device_snapshot_ins ON ingresos")
                cur.execute("DROP TRIGGER IF EXISTS trg_sync_device_snapshot_upd ON ingresos")
                cur.execute("DROP TRIGGER IF EXISTS trg_sync_device_snapshot_del ON ingresos")
                cur.execute(
                    "CREATE TRIGGER trg_sync_device_snapshot_ins AFTER INSERT ON ingresos FOR EACH ROW EXECUTE FUNCTION sync_device_snapshot()"
                )
                cur.execute(
                    """
                    CREATE TRIGGER trg_sync_device_snapshot_upd
                    AFTER UPDATE OF device_id, fecha_ingreso, fecha_creacion, ubicacion_id, alquiler_a, alquilado, faja_garantia ON ingresos
                    FOR EACH ROW EXECUTE FUNCTION sync_device_snapshot()
                    """
                )
                cur.execute(
                    "CREATE TRIGGER trg_sync_device_snapshot_del AFTER DELETE ON ingresos FOR EACH ROW EXECUTE FUNCTION sync_device_snapshot()"
                )

                # 2) Eliminar columnas legacy si existen
                for col in ("propietario_nombre", "propietario_contacto", "propietario_doc"):
                    cur.execute(
                        f"""
                        DO $$ BEGIN
                          IF EXISTS (
                              SELECT 1 FROM information_schema.columns
                               WHERE table_name='ingresos' AND column_name='{col}'
                                 AND table_schema = ANY(current_schemas(true))
                          ) THEN
                            EXECUTE 'ALTER TABLE ingresos DROP COLUMN {col}';
                          END IF;
                        END $$;
                        """
                    )

        self.stdout.write("APLICADO OK: Fase 2, ingresos sin propietario_* y triggers actualizados")

