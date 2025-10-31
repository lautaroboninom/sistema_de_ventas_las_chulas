from django.core.management.base import BaseCommand
from django.db import connection, transaction
import re


PLACEHOLDER = "\x01 000\x02"
PATTERN_EXACT = re.compile(r"^(MG|NM|NV|CE)\s\d{4}$", re.IGNORECASE)


class Command(BaseCommand):
    help = (
        "Corrige devices.numero_interno cuando vale '\x01 000\x02' copiando numero_serie solo si coincide con 'MG/NM/NV/CE ####'. "
        "Lista los casos que no matchean el formato o que colisionan con otro numero_interno."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Aplica cambios (por defecto dry-run)")

    def handle(self, *args, **opts):
        apply = bool(opts.get("apply"))

        # Cargar candidatos con placeholder
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT id, COALESCE(numero_serie, '') AS ns
                  FROM devices
                 WHERE numero_interno = %s
                ORDER BY id
                """,
                [PLACEHOLDER],
            )
            rows = cur.fetchall() or []

        to_update = []
        invalid_format = []
        conflicts = []

        def _norm_code(s: str) -> str:
            s2 = (s or "").strip().upper()
            s2 = s2.replace(" ", "").replace("-", "")
            return s2

        for rid, ns in rows:
            ns_str = (ns or "").strip()
            if not PATTERN_EXACT.match(ns_str):
                invalid_format.append((rid, ns_str))
                continue
            # Chequear conflicto con otro numero_interno (normalizado)
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                      FROM devices
                     WHERE id <> %s
                       AND REPLACE(REPLACE(UPPER(numero_interno),' ','') ,'-','') = %s
                     LIMIT 1
                    """,
                    [rid, _norm_code(ns_str)],
                )
                row = cur.fetchone()
                if row:
                    conflicts.append((rid, ns_str, int(row[0])))
                    continue
            to_update.append((rid, ns_str))

        # Reporte
        self.stdout.write(f"Candidatos con placeholder: {len(rows)}")
        self.stdout.write(f"  Para actualizar (formato OK, sin conflictos): {len(to_update)}")
        self.stdout.write(f"  Formato inválido: {len(invalid_format)}")
        self.stdout.write(f"  Conflictos por duplicado: {len(conflicts)}")

        if invalid_format:
            self.stdout.write("\nCasos con formato inválido de numero_serie (esperado 'MG/NM/NV/CE ####'):")
            for rid, ns in invalid_format[:50]:
                self.stdout.write(f"  device_id={rid} numero_serie='{ns}'")
            if len(invalid_format) > 50:
                self.stdout.write(f"  ... y {len(invalid_format) - 50} más")

        if conflicts:
            self.stdout.write("\nCasos con conflicto (otro device tiene ese numero_interno):")
            for rid, ns, other_id in conflicts[:50]:
                self.stdout.write(f"  device_id={rid} numero_serie='{ns}' conflict_with_device_id={other_id}")
            if len(conflicts) > 50:
                self.stdout.write(f"  ... y {len(conflicts) - 50} más")

        if not apply or not to_update:
            self.stdout.write("\nDRY-RUN OK (use --apply para aplicar los cambios)")
            return

        # Aplicar de forma segura en transacción
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.executemany(
                    "UPDATE devices SET numero_interno=%s WHERE id=%s",
                    [(ns, rid) for rid, ns in to_update],
                )
        self.stdout.write("\nAPLICADO: cambios realizados correctamente")

