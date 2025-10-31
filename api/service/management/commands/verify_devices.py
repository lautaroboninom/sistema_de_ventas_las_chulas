from django.core.management.base import BaseCommand
from django.db import connection
from typing import List, Tuple


class Command(BaseCommand):
    help = (
        "Verifica integridad de devices: campos expuestos en DeviceListSerializer, "
        "duplicados por numero_serie/numero_interno normalizados y consistencia de ubicacion_id con el último ingreso."
    )

    def handle(self, *args, **opts):
        # 1) Verificar campos del serializer (sin instanciar Django AppConfig completo, reportamos lista esperada)
        expected_fields = (
            "id", "customer", "marca", "model",
            "numero_serie", "numero_interno", "tipo_equipo", "variante",
            "garantia_vence", "alquilado", "alquiler_a", "ubicacion_id",
        )
        self.stdout.write("DeviceListSerializer campos esperados: " + ", ".join(expected_fields))

        # 2) Duplicados por NS normalizado
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT ns_norm, COUNT(*)
                  FROM (
                    SELECT UPPER(REPLACE(REPLACE(COALESCE(numero_serie,''),' ',''),'-','')) AS ns_norm
                      FROM devices
                     WHERE COALESCE(NULLIF(TRIM(numero_serie),''), '') <> ''
                  ) s
                 GROUP BY ns_norm
                HAVING COUNT(*) > 1
                 ORDER BY COUNT(*) DESC
                 LIMIT 20
                """
            )
            dup_ns = cur.fetchall() or []
        self.stdout.write(f"Duplicados por numero_serie normalizado: {len(dup_ns)} (muestra hasta 20)")
        for key, cnt in dup_ns:
            self.stdout.write(f"  - {key}: {cnt}")

        # 3) Duplicados por numero_interno normalizado (MG|NM|NV|CE ####)
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT numint_norm, COUNT(*)
                  FROM (
                    SELECT UPPER(REGEXP_REPLACE(COALESCE(numero_interno,''),
                             '^(MG|NM|NV|CE)\s*(\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0'))) AS numint_norm
                      FROM devices
                     WHERE numero_interno ~* '^(MG|NM|NV|CE)\s*\d{1,4}$'
                  ) s
                 GROUP BY numint_norm
                HAVING COUNT(*) > 1
                 ORDER BY COUNT(*) DESC
                 LIMIT 20
                """
            )
            dup_numint = cur.fetchall() or []
        self.stdout.write(f"Duplicados por numero_interno normalizado: {len(dup_numint)} (muestra hasta 20)")
        for key, cnt in dup_numint:
            self.stdout.write(f"  - {key}: {cnt}")

        # 4) Muestra de consistencia ubicacion_id (devices) vs último ingreso
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT d.id,
                       d.ubicacion_id AS device_ubicacion,
                       (
                         SELECT t.ubicacion_id
                           FROM ingresos t
                          WHERE t.device_id = d.id
                          ORDER BY COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
                          LIMIT 1
                       ) AS last_ubicacion
                  FROM devices d
                 ORDER BY d.id
                 LIMIT 10
                """
            )
            sample = cur.fetchall() or []

        mismatches: List[Tuple[int, int, int]] = []
        for did, d_ub, l_ub in sample:
            if (d_ub or None) != (l_ub or None):
                mismatches.append((did, d_ub, l_ub))

        self.stdout.write("Muestra de 10 devices: mismatches ubicacion_id (device vs último ingreso): " + str(len(mismatches)))
        for did, d_ub, l_ub in mismatches:
            self.stdout.write(f"  - device_id={did} device_ubic={d_ub} last_ubic={l_ub}")

        self.stdout.write("Verificación completada.")

