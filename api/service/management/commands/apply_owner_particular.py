from django.core.management.base import BaseCommand
from django.db import connection, transaction


DDL_FUNC = r"""
CREATE OR REPLACE FUNCTION sync_device_snapshot()
RETURNS TRIGGER AS $$
DECLARE
  v_device_id INTEGER;
  v_last_id INTEGER;
  v_alquilado BOOLEAN;
  v_alquiler_a TEXT;
  v_propietario_nombre TEXT;
  v_propietario_contacto TEXT;
  v_propietario_doc TEXT;
  v_faja TEXT;
  v_ubic_id INTEGER;
BEGIN
  v_device_id := COALESCE(NEW.device_id, OLD.device_id);

  -- ultimo ingreso del equipo afectado
  SELECT t.id, t.alquilado, t.alquiler_a,
         t.propietario_nombre, t.propietario_contacto, t.propietario_doc,
         t.faja_garantia, t.ubicacion_id
    INTO v_last_id, v_alquilado, v_alquiler_a,
         v_propietario_nombre, v_propietario_contacto, v_propietario_doc,
         v_faja, v_ubic_id
    FROM ingresos t
   WHERE t.device_id = v_device_id
   ORDER BY COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
   LIMIT 1;

  -- Actualizar snapshot en devices (sin heuristica MGBIO)
  UPDATE devices d
     SET alquilado = COALESCE(v_alquilado, FALSE),
         alquiler_a = v_alquiler_a,
         ubicacion_id = COALESCE(v_ubic_id, d.ubicacion_id),
         n_de_control = COALESCE(NULLIF(v_faja, ''), d.n_de_control),
         propietario = COALESCE(NULLIF(v_propietario_nombre, ''), d.propietario),
         propietario_nombre = COALESCE(NULLIF(v_propietario_nombre, ''), d.propietario_nombre),
         propietario_contacto = COALESCE(NULLIF(v_propietario_contacto, ''), d.propietario_contacto),
         propietario_doc = COALESCE(NULLIF(v_propietario_doc, ''), d.propietario_doc)
   WHERE d.id = v_device_id;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


class Command(BaseCommand):
    help = "Agrega campos de propietario en devices, asegura cliente 'Particular', actualiza triggers y backfill"

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                # 1) Asegurar columnas nuevas en devices
                cur.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS propietario_nombre TEXT")
                cur.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS propietario_contacto TEXT")
                cur.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS propietario_doc TEXT")

                # 2) Asegurar cliente 'Particular'
                cur.execute(
                    """
                    INSERT INTO customers (cod_empresa, razon_social)
                    SELECT NULL, 'Particular'
                    WHERE NOT EXISTS (
                      SELECT 1 FROM customers WHERE LOWER(razon_social) = 'particular'
                    )
                    """
                )

                # 3) Reemplazar funcion + triggers de snapshot
                cur.execute(DDL_FUNC)
                cur.execute("DROP TRIGGER IF EXISTS trg_sync_device_snapshot_ins ON ingresos")
                cur.execute("DROP TRIGGER IF EXISTS trg_sync_device_snapshot_upd ON ingresos")
                cur.execute("DROP TRIGGER IF EXISTS trg_sync_device_snapshot_del ON ingresos")
                cur.execute(
                    "CREATE TRIGGER trg_sync_device_snapshot_ins AFTER INSERT ON ingresos FOR EACH ROW EXECUTE FUNCTION sync_device_snapshot()"
                )
                cur.execute(
                    """
                    CREATE TRIGGER trg_sync_device_snapshot_upd
                    AFTER UPDATE OF device_id, fecha_ingreso, fecha_creacion, ubicacion_id, alquiler_a, alquilado, faja_garantia, propietario_nombre, propietario_contacto, propietario_doc ON ingresos
                    FOR EACH ROW EXECUTE FUNCTION sync_device_snapshot()
                    """
                )
                cur.execute(
                    "CREATE TRIGGER trg_sync_device_snapshot_del AFTER DELETE ON ingresos FOR EACH ROW EXECUTE FUNCTION sync_device_snapshot()"
                )

                # 4) Backfill desde ultimo ingreso + legacy propietario
                # 4a) desde ingresos
                cur.execute(
                    """
                    WITH last_i AS (
                      SELECT d.id AS device_id,
                             (
                               SELECT t.propietario_nombre FROM ingresos t
                                WHERE t.device_id = d.id
                                ORDER BY COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC LIMIT 1
                             ) AS p_nombre,
                             (
                               SELECT t.propietario_contacto FROM ingresos t
                                WHERE t.device_id = d.id
                                ORDER BY COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC LIMIT 1
                             ) AS p_contacto,
                             (
                               SELECT t.propietario_doc FROM ingresos t
                                WHERE t.device_id = d.id
                                ORDER BY COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC LIMIT 1
                             ) AS p_doc
                        FROM devices d
                    )
                    UPDATE devices d
                       SET propietario = COALESCE(NULLIF(li.p_nombre,''), d.propietario),
                           propietario_nombre = COALESCE(NULLIF(li.p_nombre,''), d.propietario_nombre),
                           propietario_contacto = COALESCE(NULLIF(li.p_contacto,''), d.propietario_contacto),
                           propietario_doc = COALESCE(NULLIF(li.p_doc,''), d.propietario_doc)
                      FROM last_i li
                     WHERE d.id = li.device_id
                    """
                )

                # 4b) legacy: si no hay propietario_nombre pero si propietario legacy, copiar
                cur.execute(
                    """
                    UPDATE devices
                       SET propietario_nombre = COALESCE(propietario_nombre, propietario)
                     WHERE propietario_nombre IS NULL
                       AND NULLIF(COALESCE(propietario,''),'') <> ''
                    """
                )

        self.stdout.write("APLICADO OK: owner fields en devices + Particular + triggers + backfill")

