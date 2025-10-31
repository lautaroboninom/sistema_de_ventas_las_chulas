from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Valida consistencia post-migración entre devices.numero_interno, devices.n_de_control y el snapshot en ingresos.faja_garantia"

    def handle(self, *args, **opts):
        with connection.cursor() as cur:
            self.stdout.write("==[1/8] Totales de devices")
            cur.execute(
                """
                SELECT
                  COUNT(*) AS devices_total,
                  COUNT(NULLIF(TRIM(numero_interno), '')) AS numint_no_vacio,
                  COUNT(NULLIF(TRIM(n_de_control), '')) AS ndc_no_vacio
                FROM devices
                """
            )
            row = cur.fetchone()
            self.stdout.write(f"devices_total={row[0]} numint_no_vacio={row[1]} ndc_no_vacio={row[2]}")

        with connection.cursor() as cur:
            self.stdout.write("\n==[2/8] Duplicados por numero_interno normalizado (top 50)")
            cur.execute(
                """
                WITH norm AS (
                  SELECT id,
                         UPPER(REGEXP_REPLACE(numero_interno,
                               '^(MG|NM|NV|CE)\s*(\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0'))) AS num_norm
                    FROM devices
                   WHERE numero_interno ~* '^(MG|NM|NV|CE)\s*\d{1,4}$'
                )
                SELECT num_norm, COUNT(*) AS cnt
                  FROM norm
                 GROUP BY 1
                HAVING COUNT(*) > 1
                 ORDER BY cnt DESC, num_norm
                 LIMIT 50
                """
            )
            dups = cur.fetchall() or []
            if not dups:
                self.stdout.write("OK: sin duplicados normalizados")
            else:
                for num_norm, cnt in dups:
                    self.stdout.write(f"dup {num_norm}: {cnt}")

        with connection.cursor() as cur:
            self.stdout.write("\n==[3/8] Distribución por prefijo de numero_interno")
            cur.execute(
                """
                SELECT prefijo, COUNT(*) AS cant
                FROM (
                  SELECT CASE
                           WHEN numero_interno ~* '^MG' THEN 'MG'
                           WHEN numero_interno ~* '^NM' THEN 'NM'
                           WHEN numero_interno ~* '^NV' THEN 'NV'
                           WHEN numero_interno ~* '^CE' THEN 'CE'
                           WHEN NULLIF(TRIM(numero_interno),'') IS NULL THEN 'VACIO'
                           ELSE 'OTRO'
                         END AS prefijo
                    FROM devices
                ) t
                GROUP BY prefijo
                ORDER BY prefijo
                """
            )
            for prefijo, cant in (cur.fetchall() or []):
                self.stdout.write(f"{prefijo}: {cant}")

        with connection.cursor() as cur:
            self.stdout.write("\n==[4/8] Mismatches snapshot n_de_control vs último faja_garantia")
            cur.execute(
                """
                WITH last_i AS (
                  SELECT DISTINCT ON (t.device_id)
                         t.device_id,
                         NULLIF(t.faja_garantia,'') AS faja
                    FROM ingresos t
                   ORDER BY t.device_id, COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
                )
                SELECT COUNT(*) AS mismatches
                  FROM devices d
                  JOIN last_i li ON li.device_id = d.id
                 WHERE COALESCE(NULLIF(d.n_de_control,''), '') <> COALESCE(li.faja, '')
                """
            )
            mismatches = int((cur.fetchone() or [0])[0] or 0)
            self.stdout.write(f"mismatches={mismatches}")

        with connection.cursor() as cur:
            self.stdout.write("\n    - Detalle: excluyendo faja vacía vs solo faja vacía")
            cur.execute(
                """
                WITH last_i AS (
                  SELECT DISTINCT ON (t.device_id)
                         t.device_id,
                         NULLIF(t.faja_garantia,'') AS faja
                    FROM ingresos t
                   ORDER BY t.device_id, COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
                )
                SELECT
                  SUM(CASE WHEN COALESCE(NULLIF(d.n_de_control,''), '') <> COALESCE(li.faja, '') AND COALESCE(TRIM(li.faja),'') <> '' THEN 1 ELSE 0 END) AS mismatches_excl_empty,
                  SUM(CASE WHEN COALESCE(NULLIF(d.n_de_control,''), '') <> COALESCE(li.faja, '') AND COALESCE(TRIM(li.faja),'') = '' THEN 1 ELSE 0 END) AS mismatches_only_empty
                FROM devices d
                JOIN last_i li ON li.device_id = d.id
                """
            )
            row = cur.fetchone() or [0, 0]
            self.stdout.write(f"      mismatches_excl_empty={int(row[0] or 0)} mismatches_only_empty={int(row[1] or 0)}")

        with connection.cursor() as cur:
            self.stdout.write("\n==[5/8] Muestras de mismatch (máx 20)")
            cur.execute(
                """
                WITH last_i AS (
                  SELECT DISTINCT ON (t.device_id)
                         t.device_id,
                         NULLIF(t.faja_garantia,'') AS faja,
                         COALESCE(t.fecha_ingreso, t.fecha_creacion) AS fecha_ref,
                         t.id AS ingreso_id
                    FROM ingresos t
                   ORDER BY t.device_id, COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
                )
                SELECT d.id AS device_id, d.numero_interno, d.n_de_control, li.faja AS faja_last, li.fecha_ref, li.ingreso_id
                  FROM devices d
                  JOIN last_i li ON li.device_id = d.id
                 WHERE COALESCE(NULLIF(d.n_de_control,''), '') <> COALESCE(li.faja, '')
                 ORDER BY li.fecha_ref DESC, d.id DESC
                 LIMIT 20
                """
            )
            rows = cur.fetchall() or []
            for r in rows:
                self.stdout.write(
                    f"dev={r[0]} numint='{r[1] or ''}' ndc='{r[2] or ''}' faja='{r[3] or ''}' fecha={r[4]} ingreso_id={r[5]}"
                )
            if not rows:
                self.stdout.write("(sin filas)")

        with connection.cursor() as cur:
            self.stdout.write("\n==[6/8] NDC vacío pero último faja_garantia no vacía")
            cur.execute(
                """
                WITH last_i AS (
                  SELECT DISTINCT ON (t.device_id)
                         t.device_id,
                         NULLIF(t.faja_garantia,'') AS faja
                    FROM ingresos t
                   ORDER BY t.device_id, COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
                )
                SELECT COUNT(*) AS faltantes
                  FROM devices d
                  JOIN last_i li ON li.device_id = d.id
                 WHERE NULLIF(TRIM(li.faja),'') IS NOT NULL
                   AND NULLIF(TRIM(d.n_de_control),'') IS NULL
                """
            )
            falt = int((cur.fetchone() or [0])[0] or 0)
            self.stdout.write(f"faltantes={falt}")

        with connection.cursor() as cur:
            self.stdout.write("\n==[7/8] Devices sin ingresos")
            cur.execute(
                """
                SELECT COUNT(*) AS sin_ingresos
                FROM devices d
                LEFT JOIN ingresos t ON t.device_id = d.id
                WHERE t.id IS NULL
                """
            )
            self.stdout.write(f"sin_ingresos={(cur.fetchone() or [0])[0]}")

        with connection.cursor() as cur:
            self.stdout.write("\n==[8/8] numero_interno no normalizados que parecen MG/NM/NV/CE (top 20)")
            cur.execute(
                """
                SELECT id, numero_interno
                FROM devices d
                WHERE numero_interno ~* '^(MG|NM|NV|CE)'
                  AND NOT (numero_interno ~* '^(MG|NM|NV|CE)\s*\d{1,4}$')
                ORDER BY id DESC
                LIMIT 20
                """
            )
            rows = cur.fetchall() or []
            for rid, numint in rows:
                self.stdout.write(f"id={rid} numero_interno='{(numint or '').strip()}'")
            if not rows:
                self.stdout.write("(sin filas)")
