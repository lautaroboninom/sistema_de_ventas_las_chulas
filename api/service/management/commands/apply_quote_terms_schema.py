from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Agrega columnas de condiciones comerciales en quotes"

    def handle(self, *args, **opts):
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS plazo_entrega_txt TEXT")
                cur.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS garantia_txt TEXT")
                cur.execute("ALTER TABLE quotes ADD COLUMN IF NOT EXISTS mant_oferta_txt TEXT")
        self.stdout.write("APLICADO OK: quotes (plazo_entrega_txt, garantia_txt, mant_oferta_txt)")
