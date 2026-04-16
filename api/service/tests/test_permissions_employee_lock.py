import unittest
from types import SimpleNamespace
from unittest.mock import patch

from service.permission_catalog import get_role_defaults
from service.permission_policy import VIEW_PERMISSION_MATRIX
from service.permissions import resolve_effective_permissions, validate_overrides_for_role
from service.views.retail_views import RetailVentaOperacionSolicitudView


class EmpleadoPermissionLockTests(unittest.TestCase):
    def test_resolve_effective_permissions_hard_locks_empleado(self):
        effective = resolve_effective_permissions(
            role='empleado',
            overrides={
                'action.ventas.anular': 'allow',
                'action.ventas.devolver': 'allow',
                'action.ventas.cambiar': 'allow',
                'page.reportes': 'allow',
            },
        )
        self.assertFalse(effective.get('action.ventas.anular'))
        self.assertFalse(effective.get('action.ventas.devolver'))
        self.assertFalse(effective.get('page.reportes'))
        self.assertTrue(effective.get('action.ventas.cambiar'))

    def test_validate_overrides_for_role_rejects_allow_for_locked_codes(self):
        with self.assertRaises(ValueError):
            validate_overrides_for_role(
                'empleado',
                {
                    'action.ventas.anular': 'allow',
                    'action.ventas.cambiar': 'allow',
                },
            )

    def test_permission_matrix_covers_barcodes_and_sales_requests(self):
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailVarianteBarcodesView', {}).get('GET'),
            'page.productos',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailVarianteBarcodeGenerateView', {}).get('POST'),
            'action.config.editar',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailVarianteBarcodeAssociateView', {}).get('POST'),
            'action.config.editar',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailVarianteBarcodePrimaryView', {}).get('POST'),
            'action.config.editar',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailVarianteBarcodeLabelsPdfView', {}).get('GET'),
            'page.productos',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailVentaOperacionSolicitudView', {}).get('POST'),
            'page.ventas',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailStoreCreditsView', {}).get('GET'),
            'page.pos',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailStoreCreditConsumeView', {}).get('POST'),
            'page.pos',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailCajaCierreAsistidoView', {}).get('POST'),
            'action.caja.cierre_asistido',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailOperacionPendientesView', {}).get('GET'),
            'page.pos',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailInventarioConteosView', {}).get('POST'),
            'action.inventario.conteo',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailOnlineJobsProcessView', {}).get('POST'),
            'action.online.sync',
        )
        self.assertEqual(
            VIEW_PERMISSION_MATRIX.get('RetailAlertaAckView', {}).get('POST'),
            'action.alertas.gestionar',
        )

    def test_role_defaults_include_new_retail_operation_permissions(self):
        empleado = get_role_defaults('empleado')
        admin = get_role_defaults('admin')
        self.assertIn('action.caja.cierre_asistido', empleado)
        self.assertTrue(empleado.get('action.caja.cierre_asistido'))
        self.assertFalse(empleado.get('action.postventa.credito_tienda'))
        self.assertFalse(empleado.get('action.inventario.conteo'))
        self.assertFalse(empleado.get('action.alertas.gestionar'))
        self.assertTrue(admin.get('action.postventa.credito_tienda'))
        self.assertTrue(admin.get('action.inventario.conteo'))
        self.assertTrue(admin.get('action.alertas.gestionar'))
        self.assertTrue(admin.get('action.config.online_credentials'))


class RetailVentaOperacionSolicitudViewTests(unittest.TestCase):
    def _request(self, data):
        return SimpleNamespace(
            data=data,
            user=SimpleNamespace(id=7, nombre='Empleado Test', rol='empleado'),
            method='POST',
        )

    @patch('service.views.retail_views.user_has_permission', return_value=False)
    @patch('service.views.retail_views.send_mail_checked')
    @patch('service.views.retail_views.q')
    def test_returns_config_error_when_no_admin_recipients(self, q_mock, send_mail_mock, _has_perm_mock):
        sale_row = {
            'id': 123,
            'sale_number': 'V-000123',
            'status': 'confirmed',
            'channel': 'local',
            'total_ars': '10999.00',
            'created_at': '2026-04-05T10:00:00Z',
            'customer_name': 'Cliente Test',
        }
        q_mock.side_effect = [sale_row, []]
        view = RetailVentaOperacionSolicitudView()
        response = view.post(
            self._request({'operation_code': 'cancel_sale', 'reason': 'Requiere revision admin'}),
            venta_id=123,
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data.get('code'), 'no_admin_recipients')
        send_mail_mock.assert_not_called()

    @patch('service.views.retail_views.user_has_permission', return_value=False)
    @patch('service.views.retail_views.send_mail_checked')
    @patch('service.views.retail_views.q')
    def test_sends_mail_to_active_admins(self, q_mock, send_mail_mock, _has_perm_mock):
        sale_row = {
            'id': 123,
            'sale_number': 'V-000123',
            'status': 'confirmed',
            'channel': 'local',
            'total_ars': '10999.00',
            'created_at': '2026-04-05T10:00:00Z',
            'customer_name': 'Cliente Test',
        }
        admins = [
            {'id': 1, 'nombre': 'Admin 1', 'email': 'admin1@example.com'},
            {'id': 2, 'nombre': 'Admin 2', 'email': 'admin2@example.com'},
        ]
        q_mock.side_effect = [sale_row, admins]
        send_mail_mock.return_value = {
            'ok': True,
            'status': 200,
            'detail': 'Mail enviado correctamente.',
        }

        view = RetailVentaOperacionSolicitudView()
        response = view.post(
            self._request({'operation_code': 'money_return', 'reason': 'Solicita devolucion monetaria'}),
            venta_id=123,
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data.get('ok'))
        self.assertEqual(response.data.get('operation_code'), 'money_return')
        self.assertEqual(response.data.get('delivery_summary', {}).get('sent'), 2)
        self.assertEqual(send_mail_mock.call_count, 2)


if __name__ == '__main__':
    unittest.main()
