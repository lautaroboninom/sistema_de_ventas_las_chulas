import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import django
from rest_framework.exceptions import PermissionDenied

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from service.views.system_update_views import SystemUpdateCheckView, SystemUpdateStatusView


def _user(role='empleado'):
    return SimpleNamespace(id=7, rol=role, nombre='Usuario Test')


class SystemUpdateStatusViewTests(unittest.TestCase):
    @patch('service.views.system_update_views.get_update_status')
    def test_get_returns_status_payload(self, status_mock):
        status_mock.return_value = {
            'ok': True,
            'channel': 'main',
            'pending': False,
            'installed_commit': 'abc',
            'remote_commit': 'abc',
            'last_check_at': None,
            'last_update_at': None,
            'last_error': None,
        }
        request = SimpleNamespace(user=_user(), method='GET')

        response = SystemUpdateStatusView().get(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get('ok'))
        status_mock.assert_called_once()


class SystemUpdateCheckViewTests(unittest.TestCase):
    @patch('service.views.system_update_views.run_update_check')
    def test_post_force_false_allowed_for_authenticated_user(self, check_mock):
        check_mock.return_value = {
            'ok': True,
            'channel': 'main',
            'pending': False,
            'installed_commit': 'abc',
            'remote_commit': 'abc',
            'last_check_at': None,
            'last_update_at': None,
            'last_error': None,
        }
        request = SimpleNamespace(data={'force': False}, user=_user('empleado'), method='POST')

        response = SystemUpdateCheckView().post(request)
        self.assertEqual(response.status_code, 200)
        check_mock.assert_called_once_with(force=False)

    @patch('service.views.system_update_views.run_update_check')
    def test_post_force_true_requires_admin(self, check_mock):
        request = SimpleNamespace(data={'force': True}, user=_user('empleado'), method='POST')

        with self.assertRaises(PermissionDenied):
            SystemUpdateCheckView().post(request)
        check_mock.assert_not_called()

    @patch('service.views.system_update_views.run_update_check')
    def test_post_force_true_allows_admin(self, check_mock):
        check_mock.return_value = {
            'ok': True,
            'channel': 'main',
            'pending': True,
            'installed_commit': 'abc',
            'remote_commit': 'def',
            'last_check_at': '2026-04-12T00:00:00Z',
            'last_update_at': None,
            'last_error': None,
        }
        request = SimpleNamespace(data={'force': True}, user=_user('admin'), method='POST')

        response = SystemUpdateCheckView().post(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get('pending'))
        check_mock.assert_called_once_with(force=True)

    @patch('service.views.system_update_views.run_update_check')
    def test_post_returns_500_when_update_check_fails(self, check_mock):
        check_mock.return_value = {
            'ok': False,
            'channel': 'main',
            'pending': True,
            'installed_commit': 'abc',
            'remote_commit': 'def',
            'last_check_at': '2026-04-12T00:00:00Z',
            'last_update_at': None,
            'last_error': 'git fetch fallo',
        }
        request = SimpleNamespace(data={'force': False}, user=_user('admin'), method='POST')

        response = SystemUpdateCheckView().post(request)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data.get('last_error'), 'git fetch fallo')


if __name__ == '__main__':
    unittest.main()
