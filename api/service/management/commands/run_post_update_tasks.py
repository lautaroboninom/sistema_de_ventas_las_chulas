"""Ejecuta las tareas post-actualizacion pendientes.

Pensado para correr sin supervision durante la actualizacion del cliente: nunca falla
con codigo de salida distinto de 0 para no interrumpir el arranque de la app.
"""

import json

from django.core.management.base import BaseCommand

from service.post_update_tasks import run_pending_tasks


class Command(BaseCommand):
    help = 'Ejecuta las tareas post-actualizacion pendientes (idempotente y no bloqueante).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', dest='limit', type=int, default=10)

    def handle(self, *args, **options):
        try:
            summary = run_pending_tasks(limit=options.get('limit') or 10)
        except Exception as exc:  # defensivo: el runner ya atrapa, esto es la ultima red
            self.stdout.write(self.style.WARNING(f'Tareas post-actualizacion: error inesperado ({exc})'))
            return

        if not summary.get('enabled'):
            self.stdout.write(f"Tareas post-actualizacion: {summary.get('detail') or 'desactivadas'}")
            return

        detalle = summary.get('detail')
        if detalle:
            self.stdout.write(f'Tareas post-actualizacion: {detalle}')

        self.stdout.write(
            'Tareas post-actualizacion: ejecutadas={ran} ok={done} omitidas={skipped} fallidas={failed}'.format(
                ran=summary.get('ran') or 0,
                done=summary.get('done') or 0,
                skipped=summary.get('skipped') or 0,
                failed=summary.get('failed') or 0,
            )
        )
        for task in summary.get('tasks') or []:
            self.stdout.write(f"  - {task.get('code')}: {task.get('status')}")
            result = task.get('result')
            if result:
                self.stdout.write(f'    {json.dumps(result, ensure_ascii=False)[:500]}')
