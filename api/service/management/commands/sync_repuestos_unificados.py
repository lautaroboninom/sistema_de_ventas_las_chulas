from django.core.management.base import BaseCommand
from service.repuestos import sync_catalogo_repuestos_unificados


class Command(BaseCommand):
    help = (
        "Sincroniza el catálogo de repuestos desde un Excel unificado "
        "(Col A=código, Col B=descripción/nombre, Col E=proveedor)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            dest="path",
            default=None,
            help="Ruta al .xlsx. Si no se indica, usa settings.REPUESTOS_UNIFICADOS_FILE.",
        )
        parser.add_argument("--sheet", dest="sheet", default=None)
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help="Si se indica, desactiva repuestos que no estén en el Excel.",
        )

    def handle(self, *args, **opts):
        res = sync_catalogo_repuestos_unificados(
            path=opts.get("path"),
            sheet=opts.get("sheet"),
            deactivate_missing=bool(opts.get("deactivate_missing")),
        )
        self.stdout.write(self.style.SUCCESS(f"OK: {res.get('count', 0)} repuestos sincronizados."))
        conflicts = res.get("conflicts") or []
        if conflicts:
            self.stdout.write(self.style.WARNING(f"Conflictos detectados: {len(conflicts)}"))
            for c in conflicts[:20]:
                self.stdout.write(str(c))
