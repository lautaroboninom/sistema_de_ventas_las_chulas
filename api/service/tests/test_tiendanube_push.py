import unittest
from unittest.mock import patch

from rest_framework.exceptions import ValidationError

from service.views.retail_views import (
    _tiendanube_build_product_payload_from_local_variants,
    _tiendanube_build_create_product_payload_from_local_variant,
    _tiendanube_depublish_old_products,
    _tiendanube_delete_remote_for_local_variant,
    _tiendanube_ensure_rows_remote_mapping,
    _tiendanube_run_retryable_job,
)


class TiendaNubePushTests(unittest.TestCase):
    def _local_variant(self, **overrides):
        base = {
            'id': 501,
            'producto': 'Remera Basic',
            'display_name': 'Remera Basic (talle=m)',
            'sku': 'SKU-RH-501',
            'barcode_internal': '7790000001234',
            'price_online_ars': '1500.00',
            'cost_avg_ars': '800.00',
            'stock_on_hand': 4,
            'active': True,
            'option_values': [],
        }
        base.update(overrides)
        return base

    def test_payload_with_size_uses_talle_attribute(self):
        row = self._local_variant(
            option_values=[
                {'attribute_code': 'talle', 'attribute_name': 'Talle', 'option_value': 'M'},
            ]
        )
        payload = _tiendanube_build_create_product_payload_from_local_variant(row)
        self.assertEqual(payload['name']['es'], 'Remera Basic')
        self.assertEqual(payload['attributes'], [{'es': 'Talle'}])
        self.assertEqual(payload['variants'][0]['values'], [{'es': 'M'}])
        self.assertEqual(payload['variants'][0]['sku'], 'SKU-RH-501')

    def test_payload_with_color_and_size_keeps_color_as_attribute(self):
        row = self._local_variant(
            option_values=[
                {'attribute_code': 'color', 'attribute_name': 'Color', 'option_value': 'Negro'},
                {'attribute_code': 'talle', 'attribute_name': 'Talle', 'option_value': 'L'},
            ]
        )
        payload = _tiendanube_build_create_product_payload_from_local_variant(row)
        self.assertEqual(payload['name']['es'], 'Remera Basic')
        self.assertEqual(payload['attributes'], [{'es': 'Color'}, {'es': 'Talle'}])
        self.assertEqual(payload['variants'][0]['values'], [{'es': 'Negro'}, {'es': 'L'}])

    def test_payload_with_only_color_keeps_variant_attribute(self):
        row = self._local_variant(
            option_values=[
                {'attribute_code': 'color', 'attribute_name': 'Color', 'option_value': 'Rojo'},
            ]
        )
        payload = _tiendanube_build_create_product_payload_from_local_variant(row)
        self.assertEqual(payload['name']['es'], 'Remera Basic')
        self.assertEqual(payload['attributes'], [{'es': 'Color'}])
        self.assertEqual(payload['variants'][0]['values'], [{'es': 'Rojo'}])

    def test_payload_includes_non_color_attributes(self):
        row = self._local_variant(
            option_values=[
                {'attribute_code': 'color', 'attribute_name': 'Color', 'option_value': 'Negro'},
                {'attribute_code': 'talle', 'attribute_name': 'Talle', 'option_value': 'XL'},
                {'attribute_code': 'material', 'attribute_name': 'Material', 'option_value': 'Algodon'},
            ]
        )
        payload = _tiendanube_build_create_product_payload_from_local_variant(row)
        self.assertEqual(payload['name']['es'], 'Remera Basic')
        self.assertEqual(payload['attributes'], [{'es': 'Color'}, {'es': 'Talle'}, {'es': 'Material'}])
        self.assertEqual(payload['variants'][0]['values'], [{'es': 'Negro'}, {'es': 'XL'}, {'es': 'Algodon'}])

    def test_grouped_payload_keeps_variants_under_one_product(self):
        rows = [
            self._local_variant(
                id=1,
                sku='SKU-NEG-S',
                option_values=[
                    {'attribute_code': 'color', 'attribute_name': 'Color', 'option_value': 'Negro'},
                    {'attribute_code': 'talle', 'attribute_name': 'Talle', 'option_value': 'S'},
                ],
            ),
            self._local_variant(
                id=2,
                sku='SKU-NEG-M',
                option_values=[
                    {'attribute_code': 'color', 'attribute_name': 'Color', 'option_value': 'Negro'},
                    {'attribute_code': 'talle', 'attribute_name': 'Talle', 'option_value': 'M'},
                ],
            ),
        ]
        built = _tiendanube_build_product_payload_from_local_variants({'name': 'Remera Basic'}, rows)
        payload = built['payload']
        self.assertEqual(payload['name']['es'], 'Remera Basic')
        self.assertEqual(payload['attributes'], [{'es': 'Color'}, {'es': 'Talle'}])
        self.assertEqual(len(payload['variants']), 2)
        self.assertEqual(payload['variants'][0]['values'], [{'es': 'Negro'}, {'es': 'S'}])
        self.assertEqual(payload['variants'][1]['sku'], 'SKU-NEG-M')

    def test_grouped_payload_rejects_more_than_three_attributes(self):
        row = self._local_variant(
            option_values=[
                {'attribute_code': 'color', 'attribute_name': 'Color', 'option_value': 'Negro'},
                {'attribute_code': 'talle', 'attribute_name': 'Talle', 'option_value': 'M'},
                {'attribute_code': 'material', 'attribute_name': 'Material', 'option_value': 'Algodon'},
                {'attribute_code': 'temporada', 'attribute_name': 'Temporada', 'option_value': 'Invierno'},
            ]
        )
        with self.assertRaises(ValidationError):
            _tiendanube_build_product_payload_from_local_variants({'name': 'Remera Basic'}, [row])

    @patch('service.views.retail_views._tiendanube_request')
    def test_old_remote_product_cleanup_skips_unrelated_skus(self, mock_request):
        mock_request.return_value = {
            'id': 9001,
            'variants': [
                {'id': 1, 'sku': 'SKU-LOCAL'},
                {'id': 2, 'sku': 'SKU-OTHER'},
            ],
        }
        out = _tiendanube_depublish_old_products(
            {'store_id': '1', 'access_token': 'x'},
            [9001],
            canonical_product_id=9000,
            local_skus=['SKU-LOCAL'],
        )
        self.assertEqual(out['unpublished'], 0)
        self.assertEqual(out['skipped'], [9001])
        self.assertEqual(mock_request.call_count, 1)

    def test_payload_omits_cost_when_zero(self):
        row = self._local_variant(
            cost_avg_ars='0',
            option_values=[
                {'attribute_code': 'talle', 'attribute_name': 'Talle', 'option_value': 'M'},
            ],
        )
        payload = _tiendanube_build_create_product_payload_from_local_variant(row)
        self.assertNotIn('cost', payload['variants'][0])

    @patch('service.views.retail_views.q')
    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views._tiendanube_request')
    def test_delete_remote_variant_unpublishes_instead_of_deleting_product(self, mock_request, mock_exec, mock_q):
        row = {
            'id': 21,
            'product_id': 300,
            'sku': 'SKU-DEL-1',
            'tiendanube_product_id': 7001,
            'tiendanube_variant_id': 8101,
        }
        mock_request.side_effect = [
            {'id': 7001, 'variants': [{'id': 8101}]},
            {},
        ]
        mock_q.return_value = {'cnt': 0}  # al producto local no le quedan variantes activas

        out = _tiendanube_delete_remote_for_local_variant({'store_id': '1', 'access_token': 'x'}, row)

        self.assertTrue(out['ok'])
        self.assertTrue(out['deleted'])
        self.assertEqual(out['scope'], 'unpublished')
        self.assertEqual(mock_request.call_count, 2)
        metodo, ruta = mock_request.call_args[0][1], mock_request.call_args[0][2]
        self.assertEqual((metodo, ruta), ('PUT', 'products/7001'))
        self.assertEqual(mock_request.call_args[1]['payload'], {'id': 7001, 'published': False})
        self.assertEqual(mock_exec.call_count, 1)

    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views._tiendanube_request')
    def test_delete_remote_variant_uses_variant_delete_when_many(self, mock_request, mock_exec):
        row = {
            'id': 22,
            'sku': 'SKU-DEL-2',
            'tiendanube_product_id': 7002,
            'tiendanube_variant_id': 8102,
        }
        mock_request.side_effect = [
            {'id': 7002, 'variants': [{'id': 8102}, {'id': 8103}]},
            {},
        ]

        out = _tiendanube_delete_remote_for_local_variant({'store_id': '1', 'access_token': 'x'}, row)

        self.assertTrue(out['ok'])
        self.assertTrue(out['deleted'])
        self.assertEqual(out['scope'], 'variant')
        self.assertEqual(mock_request.call_count, 2)
        self.assertEqual(mock_exec.call_count, 1)

    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views._tiendanube_request')
    def test_delete_remote_variant_skips_when_not_mapped(self, mock_request, mock_exec):
        row = {
            'id': 23,
            'sku': '',
            'tiendanube_product_id': None,
            'tiendanube_variant_id': None,
        }

        out = _tiendanube_delete_remote_for_local_variant({'store_id': '1', 'access_token': 'x'}, row)

        self.assertTrue(out['ok'])
        self.assertFalse(out['deleted'])
        self.assertEqual(out['scope'], 'not_mapped')
        mock_request.assert_not_called()
        mock_exec.assert_not_called()

    @patch('service.views.retail_views._tiendanube_sync_local_product_group')
    @patch('service.views.retail_views._tiendanube_autolink_rows_by_sku')
    def test_ensure_mapping_uses_autolink_without_create(self, mock_autolink, mock_group_sync):
        rows = [{'id': 10, 'product_id': 40, 'sku': 'SKU-AUTO', 'tiendanube_product_id': None, 'tiendanube_variant_id': None}]

        def _do_autolink(_cfg, target_rows):
            target_rows[0]['tiendanube_product_id'] = 9001
            target_rows[0]['tiendanube_variant_id'] = 9002
            return {'auto_mapped': 1, 'pending_mapping': 0, 'errors': []}

        mock_autolink.side_effect = _do_autolink
        out = _tiendanube_ensure_rows_remote_mapping({'store_id': '1', 'access_token': 'x'}, rows, reason='test')

        self.assertEqual(out['auto_mapped'], 1)
        self.assertEqual(out['created_remote'], 0)
        self.assertEqual(out['creation_failed'], 0)
        self.assertEqual(out['pending_mapping'], 0)
        mock_group_sync.assert_not_called()

    @patch('service.views.retail_views._tiendanube_load_local_product_group')
    @patch('service.views.retail_views._tiendanube_sync_local_product_group')
    @patch('service.views.retail_views._tiendanube_autolink_rows_by_sku')
    def test_ensure_mapping_creates_and_persists_mapping(self, mock_autolink, mock_group_sync, mock_load_group):
        rows = [{'id': 11, 'product_id': 41, 'sku': 'SKU-NEW', 'tiendanube_product_id': None, 'tiendanube_variant_id': None}]
        mock_autolink.return_value = {'auto_mapped': 0, 'pending_mapping': 1, 'errors': []}
        mock_group_sync.return_value = {'created_remote': 1}
        mock_load_group.return_value = [
            {'id': 11, 'tiendanube_product_id': 4001, 'tiendanube_variant_id': 5001},
        ]

        out = _tiendanube_ensure_rows_remote_mapping({'store_id': '1', 'access_token': 'x'}, rows, reason='test')

        self.assertEqual(out['created_remote'], 1)
        self.assertEqual(out['creation_failed'], 0)
        self.assertEqual(out['pending_mapping'], 0)
        self.assertEqual(rows[0]['tiendanube_product_id'], 4001)
        self.assertEqual(rows[0]['tiendanube_variant_id'], 5001)
        mock_group_sync.assert_called_once()

    @patch('service.views.retail_views._tiendanube_sync_local_product_group')
    @patch('service.views.retail_views._tiendanube_autolink_rows_by_sku')
    def test_ensure_mapping_creation_error_is_non_blocking(self, mock_autolink, mock_group_sync):
        rows = [{'id': 12, 'product_id': 42, 'sku': 'SKU-ERR', 'producto': 'Producto Err', 'tiendanube_product_id': None, 'tiendanube_variant_id': None}]
        mock_autolink.return_value = {'auto_mapped': 0, 'pending_mapping': 1, 'errors': []}
        mock_group_sync.side_effect = ValidationError('fallo remoto')

        out = _tiendanube_ensure_rows_remote_mapping({'store_id': '1', 'access_token': 'x'}, rows, reason='test')

        self.assertEqual(out['created_remote'], 0)
        self.assertEqual(out['creation_failed'], 1)
        self.assertEqual(out['pending_mapping'], 1)
        self.assertTrue(any('fallo remoto' in msg.lower() for msg in out['errors']))

    @patch('service.views.retail_views._tiendanube_run_sync_stock_job')
    @patch('service.views.retail_views._tiendanube_run_sync_catalogo_job')
    @patch('service.views.retail_views._tiendanube_run_import_catalogo_job')
    def test_retry_dispatch_uses_expected_runner(self, mock_import, mock_catalog, mock_stock):
        mock_import.return_value = {'status_code': 200, 'body': {'ok': True}}
        mock_catalog.return_value = {'status_code': 200, 'body': {'ok': True}}
        mock_stock.return_value = {'status_code': 200, 'body': {'ok': True}}

        out_import = _tiendanube_run_retryable_job(11, 'import_catalogo', {'limit_products': 20}, created_by=7)
        out_catalog = _tiendanube_run_retryable_job(12, 'sync_catalogo', {'limit': 30}, created_by=7)
        out_stock = _tiendanube_run_retryable_job(13, 'sync_stock', {'limit': 40}, created_by=7)

        self.assertEqual(out_import['status_code'], 200)
        self.assertEqual(out_catalog['status_code'], 200)
        self.assertEqual(out_stock['status_code'], 200)
        mock_import.assert_called_once()
        mock_catalog.assert_called_once()
        mock_stock.assert_called_once()

    @patch('service.views.retail_views._job_set_failed')
    def test_retry_dispatch_rejects_unknown_job_type(self, mock_job_failed):
        out = _tiendanube_run_retryable_job(91, 'unknown_type', {}, created_by=1)
        self.assertEqual(out['status_code'], 400)
        self.assertFalse(out['body']['ok'])
        self.assertIn('no soportado', out['body']['detail'].lower())
        mock_job_failed.assert_called_once()


if __name__ == '__main__':
    unittest.main()
