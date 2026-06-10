import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rest_framework.exceptions import ValidationError

from service.views.retail_views import (
    RetailAtributoDetailView,
    RetailAtributosView,
    RetailComprasView,
    RetailProductosView,
    RetailVarianteBarcodePrimaryView,
    RetailVarianteDetailView,
    RetailVariantesView,
    _display_option_value,
    _normalized_option_key,
    _resolve_attribute_value,
)


def _request(*, data=None, query=None, method='GET', role='admin'):
    return SimpleNamespace(
        data=data or {},
        query_params=query or {},
        user=SimpleNamespace(id=17, rol=role),
        method=method,
    )


class RetailCatalogManagementTests(unittest.TestCase):
    def test_option_value_normalization_key_is_case_accent_and_space_insensitive(self):
        self.assertEqual(_normalized_option_key('  NEGRO  '), 'negro')
        self.assertEqual(_normalized_option_key('Marron  claro'), 'marron claro')
        self.assertEqual(_normalized_option_key('marr\u00f3n'), 'marron')
        self.assertEqual(_display_option_value('NEGRO', {'code': 'color'}), 'Negro')
        self.assertEqual(_display_option_value('m', {'code': 'talle'}), 'M')

    @patch('service.views.retail_views._set_audit_user')
    @patch('service.views.retail_views.q')
    def test_atributo_post_rejects_case_duplicate(self, q_mock, _set_audit_user_mock):
        q_mock.return_value = [{'id': 3, 'name': 'Color', 'code': 'color'}]
        req = _request(data={'name': 'COLOR', 'code': 'COLOR'}, method='POST')
        with self.assertRaises(ValidationError):
            RetailAtributosView.post.__wrapped__(RetailAtributosView(), req)

    @patch('service.views.retail_views.exec_returning')
    @patch('service.views.retail_views.q')
    def test_option_value_typo_requires_confirmation(self, q_mock, exec_returning_mock):
        q_mock.side_effect = [
            None,
            [{'id': 9, 'attribute_id': 2, 'value_label': 'Negro', 'value_key': 'negro', 'active': True}],
        ]
        with self.assertRaises(ValidationError) as ctx:
            _resolve_attribute_value({'id': 2, 'code': 'color', 'name': 'Color'}, 'Nerog', confirm_new_value=False)
        self.assertIn('Negro', str(ctx.exception))
        exec_returning_mock.assert_not_called()

    @patch('service.views.retail_views.exec_returning', return_value=15)
    @patch('service.views.retail_views.q')
    def test_option_value_creates_when_no_similar_value_exists(self, q_mock, exec_returning_mock):
        q_mock.side_effect = [
            None,
            [],
            {'id': 15, 'value_label': 'Chocolate', 'value_key': 'chocolate'},
        ]
        out = _resolve_attribute_value({'id': 2, 'code': 'color', 'name': 'Color'}, 'chocolate', confirm_new_value=False)
        self.assertEqual(out['id'], 15)
        self.assertEqual(out['label'], 'Chocolate')
        exec_returning_mock.assert_called_once()

    @patch('service.views.retail_views.q')
    def test_productos_get_supports_limit(self, q_mock):
        q_mock.return_value = []
        req = _request(query={'active': '1', 'limit': '7'}, method='GET')
        response = RetailProductosView().get(req)
        self.assertEqual(response.status_code, 200)
        sql = str(q_mock.call_args[0][0])
        params = q_mock.call_args[0][1]
        self.assertIn('LIMIT %s', sql)
        self.assertIn('default_price_store_ars', sql)
        self.assertIn('default_price_online_ars', sql)
        self.assertEqual(params[-1], 7)

    @patch('service.views.retail_views.q')
    def test_variantes_get_includes_last_purchase_defaults(self, q_mock):
        q_mock.side_effect = [[], []]
        req = _request(query={'active': '1', 'limit': '10'}, method='GET')
        response = RetailVariantesView().get(req)
        self.assertEqual(response.status_code, 200)
        sql = str(q_mock.call_args_list[0][0][0])
        self.assertIn('LEFT JOIN LATERAL', sql)
        self.assertIn('last_purchase_unit_cost_currency', sql)
        self.assertIn('last_purchase_suggested_markup_pct', sql)
        self.assertIn('last_purchase_supplier_product_name', sql)
        self.assertIn('last_purchase_date', sql)
        self.assertIn('last_purchase_supplier_id', sql)
        self.assertIn('last_purchase_supplier_name', sql)
        self.assertIn('last_purchase_supplier_ean_code', sql)
        self.assertIn('last_purchase_invoice_number', sql)
        self.assertIn('LEFT JOIN retail_suppliers sp', sql)

    @patch('service.views.retail_views._can_view_costs', return_value=False)
    @patch('service.views.retail_views.q')
    def test_variantes_get_hides_purchase_cost_defaults_without_permission(self, q_mock, _can_view_costs_mock):
        q_mock.side_effect = [
            [
                {
                    'id': 1,
                    'product_id': 2,
                    'producto': 'Remera',
                    'marca': '',
                    'product_image_path': '',
                    'option_signature': 'talle=s',
                    'display_name': 'Remera S',
                    'sku': 'SKU-1',
                    'barcode_internal': '7791234567890',
                    'price_store_ars': 100,
                    'price_online_ars': 100,
                    'cost_avg_ars': 55,
                    'stock_on_hand': 8,
                    'stock_reserved': 0,
                    'stock_min': 1,
                    'last_purchase_quantity': 3,
                    'last_purchase_unit_cost_currency': 120,
                    'last_purchase_suggested_markup_pct': 45,
                    'last_purchase_supplier_product_name': 'Remera proveedor',
                    'last_purchase_date': '2026-06-01',
                    'last_purchase_supplier_id': 7,
                    'last_purchase_supplier_name': 'Proveedor X',
                    'last_purchase_supplier_ean_code': '1234',
                    'last_purchase_invoice_number': 'FAC-9',
                    'barcode_count': 1,
                    'active': True,
                    'created_at': None,
                    'updated_at': None,
                    'tiendanube_product_id': None,
                    'tiendanube_variant_id': None,
                }
            ],
            [],
            [],
        ]
        req = _request(query={'active': '1'}, method='GET')
        response = RetailVariantesView().get(req)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertIsNone(row.get('cost_avg_ars'))
        self.assertIsNone(row.get('last_purchase_unit_cost_currency'))
        self.assertIsNone(row.get('last_purchase_suggested_markup_pct'))
        self.assertEqual(row.get('last_purchase_quantity'), 3)
        self.assertEqual(row.get('last_purchase_supplier_product_name'), 'Remera proveedor')
        self.assertEqual(row.get('last_purchase_date'), '2026-06-01')
        self.assertEqual(row.get('last_purchase_supplier_id'), 7)
        self.assertEqual(row.get('last_purchase_supplier_name'), 'Proveedor X')
        self.assertEqual(row.get('last_purchase_supplier_ean_code'), '1234')
        self.assertEqual(row.get('last_purchase_invoice_number'), 'FAC-9')

    @patch('service.views.retail_views._load_compra', return_value={'id': 99, 'items': []})
    @patch('service.views.retail_views._tiendanube_schedule_local_variants_sync')
    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views.exec_returning', return_value=99)
    @patch('service.views.retail_views._set_audit_user')
    @patch('service.views.retail_views.q')
    def test_compra_post_stores_supplier_product_name_and_propagates_product_price(
        self,
        q_mock,
        _set_audit_user_mock,
        _exec_returning_mock,
        exec_void_mock,
        _schedule_sync_mock,
        _load_compra_mock,
    ):
        q_mock.side_effect = [
            {'purchase_default_markup_pct': 100},
            {'id': 5, 'product_id': 42, 'stock_on_hand': 1, 'cost_avg_ars': 10},
        ]
        req = _request(
            data={
                'supplier_id': 3,
                'currency_code': 'ARS',
                'items': [
                    {
                        'variant_id': 5,
                        'supplier_product_name': 'Jean Wideleg FIA ceniza',
                        'quantity': 2,
                        'unit_cost_currency': 50,
                        'suggested_markup_pct': 100,
                        'unit_price_final_ars': 150,
                    }
                ],
            },
            method='POST',
        )

        response = RetailComprasView.post.__wrapped__(RetailComprasView(), req)

        self.assertEqual(response.status_code, 201)
        insert_calls = [call for call in exec_void_mock.call_args_list if 'INSERT INTO retail_purchase_items' in str(call[0][0])]
        self.assertEqual(len(insert_calls), 1)
        self.assertIn('supplier_product_name', str(insert_calls[0][0][0]))
        self.assertIn('Jean Wideleg FIA ceniza', insert_calls[0][0][1])
        price_calls = [call for call in exec_void_mock.call_args_list if 'UPDATE retail_product_variants SET price_store_ars' in str(call[0][0])]
        self.assertEqual(len(price_calls), 1)
        self.assertEqual(price_calls[0][0][1][-1], 42)

    @patch('service.views.retail_views._set_audit_user')
    @patch('service.views.retail_views.q')
    def test_atributo_patch_blocks_code_change_when_in_use(self, q_mock, _set_audit_user_mock):
        q_mock.side_effect = [
            {
                'id': 11,
                'name': 'Talle',
                'code': 'talle',
                'applies_to_category_id': None,
                'active': True,
                'sort_order': 100,
            },
            [],
            {'exists': 1},
        ]
        req = _request(data={'code': 'tamano'}, method='PATCH')
        with self.assertRaises(ValidationError):
            RetailAtributoDetailView.patch.__wrapped__(RetailAtributoDetailView(), req, atributo_id=11)

    @patch('service.views.retail_views._set_audit_user')
    @patch('service.views.retail_views._tiendanube_schedule_local_variants_delete')
    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views._variant_has_operational_usage', return_value=True)
    @patch('service.views.retail_views._load_variante')
    def test_variante_delete_soft_when_has_usage(
        self,
        load_mock,
        _usage_mock,
        exec_void_mock,
        schedule_delete_mock,
        _set_audit_user_mock,
    ):
        load_mock.side_effect = [
            {'id': 51, 'active': True, 'sku': 'SKU-51'},
            {'id': 51, 'active': False, 'sku': 'SKU-51'},
        ]
        req = _request(method='DELETE')
        response = RetailVarianteDetailView.delete.__wrapped__(RetailVarianteDetailView(), req, variante_id=51)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('mode'), 'soft')
        schedule_delete_mock.assert_called_once()
        exec_void_mock.assert_called_once()

    @patch('service.views.retail_views._set_audit_user')
    @patch('service.views.retail_views._variant_try_remote_delete_best_effort')
    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views._variant_has_operational_usage', return_value=False)
    @patch('service.views.retail_views._load_variante', return_value={'id': 77, 'active': True, 'sku': 'SKU-77'})
    def test_variante_delete_hard_when_no_usage(
        self,
        _load_mock,
        _usage_mock,
        exec_void_mock,
        remote_delete_mock,
        _set_audit_user_mock,
    ):
        req = _request(method='DELETE')
        response = RetailVarianteDetailView.delete.__wrapped__(RetailVarianteDetailView(), req, variante_id=77)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.get('mode'), 'hard')
        exec_void_mock.assert_called_once()
        remote_delete_mock.assert_called_once()

    @patch('service.views.retail_views._set_audit_user')
    @patch('service.views.retail_views._tiendanube_schedule_local_variants_sync')
    @patch('service.views.retail_views._associate_variant_barcode')
    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views._load_variante')
    def test_variante_patch_barcode_schedules_catalog_sync(
        self,
        load_mock,
        exec_void_mock,
        associate_mock,
        schedule_sync_mock,
        _set_audit_user_mock,
    ):
        load_mock.side_effect = [
            {'id': 51, 'product_id': 9, 'sku': 'SKU-51', 'barcode_internal': '7791234567890'},
            {'id': 51, 'product_id': 9, 'sku': 'SKU-51', 'barcode_internal': '7791234567891'},
        ]
        req = _request(data={'barcode_internal': '7791234567891'}, method='PATCH')

        response = RetailVarianteDetailView.patch.__wrapped__(RetailVarianteDetailView(), req, variante_id=51)

        self.assertEqual(response.status_code, 200)
        associate_mock.assert_called_once()
        schedule_sync_mock.assert_called_once_with([51], sync_catalog=True, reason='variant_barcode_update')
        exec_void_mock.assert_not_called()

    @patch('service.views.retail_views._set_audit_user')
    @patch('service.views.retail_views._tiendanube_schedule_local_variants_sync')
    @patch('service.views.retail_views._associate_variant_barcode')
    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views._load_variante')
    def test_variante_patch_same_barcode_does_not_revalidate_barcode(
        self,
        load_mock,
        exec_void_mock,
        associate_mock,
        schedule_sync_mock,
        _set_audit_user_mock,
    ):
        load_mock.side_effect = [
            {'id': 51, 'product_id': 9, 'sku': 'SKU-51', 'barcode_internal': '7791234000025'},
            {'id': 51, 'product_id': 9, 'sku': 'SKU-51', 'barcode_internal': '7791234000025'},
        ]
        req = _request(data={'barcode_internal': '7791234000025'}, method='PATCH')

        response = RetailVarianteDetailView.patch.__wrapped__(RetailVarianteDetailView(), req, variante_id=51)

        self.assertEqual(response.status_code, 200)
        associate_mock.assert_not_called()
        schedule_sync_mock.assert_not_called()
        exec_void_mock.assert_not_called()

    @patch('service.views.retail_views._set_audit_user')
    @patch('service.views.retail_views._tiendanube_schedule_local_variants_sync')
    @patch('service.views.retail_views._sync_variant_primary_barcode')
    @patch('service.views.retail_views._set_variant_primary_barcode')
    @patch('service.views.retail_views._load_variante')
    @patch('service.views.retail_views.q')
    def test_barcode_primary_schedules_catalog_sync(
        self,
        q_mock,
        load_mock,
        set_primary_mock,
        sync_primary_mock,
        schedule_sync_mock,
        _set_audit_user_mock,
    ):
        q_mock.side_effect = [
            {'id': 88},
            [
                {
                    'id': 88,
                    'variant_id': 51,
                    'barcode': '7791234000025',
                    'is_primary': True,
                    'supplier_id': None,
                    'source': 'manual',
                    'created_by': None,
                    'created_at': None,
                    'updated_at': None,
                    'supplier_name': '',
                    'supplier_ean_code': '',
                }
            ],
        ]
        load_mock.return_value = {'id': 51, 'sku': 'SKU-51'}
        req = _request(data={'barcode_id': 88}, method='POST')

        response = RetailVarianteBarcodePrimaryView.post.__wrapped__(RetailVarianteBarcodePrimaryView(), req, variante_id=51)

        self.assertEqual(response.status_code, 200)
        set_primary_mock.assert_called_once_with(51, 88)
        sync_primary_mock.assert_called_once_with(51)
        schedule_sync_mock.assert_called_once_with([51], sync_catalog=True, reason='variant_barcode_primary')


if __name__ == '__main__':
    unittest.main()
