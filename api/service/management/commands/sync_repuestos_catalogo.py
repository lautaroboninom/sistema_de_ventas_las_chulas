from django.core.management.base import BaseCommand

from ...repuestos import sync_catalogo_repuestos


class Command(BaseCommand):
    help = "Sincroniza catalogo de repuestos desde Excel"

    def add_arguments(self, parser):
        parser.add_argument("--file", dest="file", default=None, help="Ruta del Excel de costos")
        parser.add_argument("--sheet", dest="sheet", default=None, help="Nombre de hoja (opcional)")
        parser.add_argument(
            "--keep-missing",
            action="store_true",
            help="No desactivar repuestos que no estan en el Excel actual",
        )

    def handle(self, *args, **opts):
        file_path = opts.get("file")
        sheet = opts.get("sheet")
        deactivate_missing = not opts.get("keep_missing")
        res = sync_catalogo_repuestos(path=file_path, sheet=sheet, deactivate_missing=deactivate_missing)
        conflicts = res.get("conflicts") or []
        self.stdout.write(f"OK repuestos={res.get('count', 0)} conflictos={len(conflicts)}")
        if conflicts:
            self.stdout.write("Conflictos (primeros 10):")
            for row in conflicts[:10]:
                self.stdout.write(
                    f"- codigo={row.get('codigo')} prev='{row.get('nombre_prev')}' new='{row.get('nombre_new')}'"
                )
