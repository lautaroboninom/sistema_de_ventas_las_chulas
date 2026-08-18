"""Endpoints que exponen y disparan las tareas post-actualizacion."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from service.views.system_update_views import (
    SystemPostUpdateRunView,
    SystemPostUpdateStatusView,
)


def _user(role='empleado'):
    return SimpleNamespace(id=7, rol=role, nombre='Usuario Test')


class SystemPostUpdateStatusViewTests(unittest.TestCase):
    @patch('service.views.system_update_views.get_tasks_status')
    def test_get_returns_task_status(self, status_mock):
        status_mock.return_value = {
            'ok': True,
            'enabled': True,
            'tasks': [{'code': 'demo', 'status': 'done', 'result': {'republicados': ['Petra']}}],
        }
        request = SimpleNamespace(user=_user(), method='GET')

        response = SystemPostUpdateStatusView().get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['tasks'][0]['status'], 'done')
        status_mock.assert_called_once()


class SystemPostUpdateRunViewTests(unittest.TestCase):
    @patch('service.views.system_update_views.get_tasks_status')
    @patch('service.views.system_update_views.run_pending_tasks')
    def test_post_runs_tasks_and_returns_status(self, run_mock, status_mock):
        run_mock.return_value = {'ok': True, 'enabled': True, 'ran': 1, 'done': 1, 'failed': 0, 'skipped': 0, 'tasks': []}
        status_mock.return_value = {'ok': True, 'enabled': True, 'tasks': []}
        request = SimpleNamespace(data={}, user=_user('empleado'), method='POST')

        response = SystemPostUpdateRunView().post(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['ok'])
        self.assertEqual(response.data['done'], 1)
        self.assertIn('status', response.data)
        run_mock.assert_called_once_with(limit=10)

    @patch('service.views.system_update_views.get_tasks_status')
    @patch('service.views.system_update_views.run_pending_tasks')
    def test_post_returns_200_even_when_tasks_failed(self, run_mock, status_mock):
        # No debe romperle la pantalla al usuario: el detalle queda en la tarea.
        run_mock.return_value = {'ok': False, 'enabled': True, 'ran': 1, 'done': 0, 'failed': 1, 'skipped': 0, 'tasks': []}
        status_mock.return_value = {'ok': True, 'enabled': True, 'tasks': []}
        request = SimpleNamespace(data={}, user=_user('empleado'), method='POST')

        response = SystemPostUpdateRunView().post(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['ok'])
        self.assertEqual(response.data['failed'], 1)


if __name__ == '__main__':
    unittest.main()
