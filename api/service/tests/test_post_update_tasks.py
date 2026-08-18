"""Tests del motor de tareas post-actualizacion.

Lo critico aca es que este runner corre solo en la maquina del cliente durante la
actualizacion: no puede propagar excepciones ni repetir trabajo ya hecho.
"""

import os
import unittest
from unittest.mock import patch

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from service import post_update_tasks as put


class FakeTasksTable:
    """Doble en memoria de `retail_post_update_tasks`."""

    def __init__(self, tasks):
        self.tasks = [dict(item) for item in tasks]

    def pending(self, limit):
        return [
            dict(item)
            for item in self.tasks
            if item['status'] in ('pending', 'failed', 'skipped')
            and int(item.get('attempts') or 0) < int(item.get('max_attempts') or 3)
        ][: int(limit)]

    def by_id(self, task_id):
        for item in self.tasks:
            if item['id'] == task_id:
                return item
        return None

    def mark_running(self, task_id):
        row = self.by_id(task_id)
        row['status'] = 'running'
        row['attempts'] = int(row.get('attempts') or 0) + 1

    def mark_finished(self, task_id, status, result=None, last_error=None):
        row = self.by_id(task_id)
        row['status'] = status
        row['result'] = result or {}
        row['last_error'] = last_error


def _task(code, **overrides):
    base = {
        'id': 1,
        'code': code,
        'title': 'Tarea de prueba',
        'status': 'pending',
        'attempts': 0,
        'max_attempts': 3,
        'payload': {},
    }
    base.update(overrides)
    return base


def _patched_runner(table):
    return [
        patch.object(put, '_table_exists', return_value=True),
        patch.object(put, '_acquire_lock', return_value=True),
        patch.object(put, '_release_lock', return_value=None),
        patch.object(put, '_pending_tasks', side_effect=table.pending),
        patch.object(put, '_mark_running', side_effect=table.mark_running),
        patch.object(put, '_mark_finished', side_effect=table.mark_finished),
    ]


class RunPendingTasksTests(unittest.TestCase):
    def _run(self, table, registry):
        parches = _patched_runner(table) + [patch.object(put, 'TASK_REGISTRY', registry)]
        for p in parches:
            p.start()
        try:
            return put.run_pending_tasks(limit=10)
        finally:
            for p in reversed(parches):
                p.stop()

    def test_marks_task_done_and_stores_result(self):
        table = FakeTasksTable([_task('demo')])
        out = self._run(table, {'demo': lambda payload: ('done', {'revisados': 3})})

        self.assertTrue(out['ok'])
        self.assertEqual(out['done'], 1)
        self.assertEqual(table.by_id(1)['status'], 'done')
        self.assertEqual(table.by_id(1)['result'], {'revisados': 3})

    def test_second_run_does_not_repeat_completed_task(self):
        table = FakeTasksTable([_task('demo')])
        llamadas = []

        def handler(payload):
            llamadas.append(payload)
            return 'done', {}

        self._run(table, {'demo': handler})
        segunda = self._run(table, {'demo': handler})

        self.assertEqual(len(llamadas), 1)
        self.assertEqual(segunda['ran'], 0)

    def test_task_exception_is_recorded_and_never_propagates(self):
        table = FakeTasksTable([_task('demo')])

        def handler(payload):
            raise RuntimeError('Tienda Nube caida')

        out = self._run(table, {'demo': handler})

        self.assertFalse(out['ok'])
        self.assertEqual(out['failed'], 1)
        self.assertEqual(table.by_id(1)['status'], 'failed')
        self.assertIn('Tienda Nube caida', table.by_id(1)['last_error'])

    def test_failed_task_retries_until_max_attempts(self):
        table = FakeTasksTable([_task('demo', max_attempts=2)])

        def handler(payload):
            raise RuntimeError('sigue fallando')

        self._run(table, {'demo': handler})
        self._run(table, {'demo': handler})
        tercera = self._run(table, {'demo': handler})

        self.assertEqual(table.by_id(1)['attempts'], 2)
        self.assertEqual(tercera['ran'], 0)

    def test_skipped_status_is_reported(self):
        table = FakeTasksTable([_task('demo')])
        out = self._run(table, {'demo': lambda payload: ('skipped', {'motivo': 'sin credenciales'})})

        self.assertTrue(out['ok'])
        self.assertEqual(out['skipped'], 1)
        self.assertEqual(table.by_id(1)['status'], 'skipped')

    def test_unknown_task_code_is_left_pending(self):
        table = FakeTasksTable([_task('tarea_de_version_futura')])
        out = self._run(table, {'demo': lambda payload: ('done', {})})

        self.assertEqual(out['ran'], 0)
        self.assertEqual(table.by_id(1)['status'], 'pending')

    def test_disabled_by_env_does_nothing(self):
        table = FakeTasksTable([_task('demo')])
        with patch.dict(os.environ, {put.TASKS_ENABLED_ENV: '0'}):
            out = self._run(table, {'demo': lambda payload: ('done', {})})

        self.assertFalse(out['enabled'])
        self.assertEqual(out['ran'], 0)
        self.assertEqual(table.by_id(1)['status'], 'pending')

    def test_missing_table_does_not_fail(self):
        with patch.object(put, '_table_exists', return_value=False):
            out = put.run_pending_tasks()
        self.assertTrue(out['ok'])
        self.assertEqual(out['ran'], 0)

    def test_db_error_does_not_propagate(self):
        with patch.object(put, '_table_exists', side_effect=RuntimeError('sin conexion')):
            out = put.run_pending_tasks()
        self.assertFalse(out['ok'])
        self.assertIn('sin conexion', out['detail'])

    def test_concurrent_run_is_skipped(self):
        table = FakeTasksTable([_task('demo')])
        parches = _patched_runner(table)
        parches[1] = patch.object(put, '_acquire_lock', return_value=False)
        for p in parches:
            p.start()
        try:
            out = put.run_pending_tasks()
        finally:
            for p in reversed(parches):
                p.stop()

        self.assertEqual(out['ran'], 0)
        self.assertIn('otra corrida', out['detail'])


class RepublishTaskTests(unittest.TestCase):
    def test_skips_when_tiendanube_not_configured(self):
        with patch('service.views.retail_views._tiendanube_cfg', return_value={}):
            status, result = put._task_tiendanube_republish_orphan_products({})

        self.assertEqual(status, 'skipped')
        self.assertIn('no esta configurado', result['motivo'])

    def test_republishes_all_unlinked_products(self):
        respuestas = [
            [{'id': 77, 'name': 'Pantalon Sastrero Petra'}, {'id': 78, 'name': 'Remera Basica'}],
        ]
        sincronizados = []

        def fake_sync(cfg, product_id, **kwargs):
            sincronizados.append(product_id)
            return {'created_remote': 6 if product_id == 77 else 0, 'product_id': 900 + product_id}

        with patch('service.views.retail_views._tiendanube_cfg', return_value={'store_id': '1', 'access_token': 'x'}), \
             patch('service.views.retail_views._tiendanube_sync_local_product_group', side_effect=fake_sync), \
             patch.object(put, '_query', side_effect=lambda *a, **k: respuestas.pop(0)):
            status, result = put._task_tiendanube_republish_orphan_products({})

        self.assertEqual(status, 'done')
        self.assertEqual(sincronizados, [77, 78])
        self.assertEqual(result['republicados'], ['Pantalon Sastrero Petra'])
        self.assertEqual(result['vinculados'], 1)
        self.assertEqual(result['con_error'], [])

    def test_product_error_does_not_stop_the_rest(self):
        respuestas = [
            [{'id': 77, 'name': 'Petra'}, {'id': 78, 'name': 'Remera'}],
        ]

        def fake_sync(cfg, product_id, **kwargs):
            if product_id == 77:
                raise RuntimeError('SKU duplicado')
            return {'created_remote': 1}

        with patch('service.views.retail_views._tiendanube_cfg', return_value={'store_id': '1', 'access_token': 'x'}), \
             patch('service.views.retail_views._tiendanube_sync_local_product_group', side_effect=fake_sync), \
             patch.object(put, '_query', side_effect=lambda *a, **k: respuestas.pop(0)):
            status, result = put._task_tiendanube_republish_orphan_products({})

        self.assertEqual(status, 'done')
        self.assertEqual(result['republicados'], ['Remera'])
        self.assertEqual(result['con_error'], [{'producto': 'Petra', 'motivo': 'SKU duplicado'}])


if __name__ == '__main__':
    unittest.main()
