import json

from django.core.management.base import BaseCommand

from service.views.retail_views import process_arca_jobs


class Command(BaseCommand):
    help = 'Procesa cola de reintentos ARCA (invoice_issue / credit_note_issue)'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20, help='Cantidad maxima de jobs a procesar')
        parser.add_argument('--max-attempts', type=int, default=8, help='Intentos maximos antes de dead_letter')

    def handle(self, *args, **options):
        limit = int(options.get('limit') or 20)
        max_attempts = int(options.get('max_attempts') or 8)
        out = process_arca_jobs(limit=limit, max_attempts=max_attempts)
        self.stdout.write(json.dumps(out, ensure_ascii=False))
