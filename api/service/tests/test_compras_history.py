from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rest_framework.exceptions import ValidationError

from service.views.retail_views import RetailComprasView


def _request(data=None, role='admin'):
    return SimpleNamespace(
        data=data or {},
        query_params={},
        user=SimpleNamespace(id=7, rol=role),
        method='POST' if data is not None else 'GET',
    )


def _q_side_effect(sql, params=None, one=False):
    text = str(sql)
    if 'SELECT id FROM retail_suppliers WHERE LOWER(name)=LOWER(%s)' in text:
        return {'id': 77}
    if 'SELECT purchase_default_markup_pct FROM retail_settings WHERE id=1' in text:
        return {'purchase_default_markup_pct': '100.00'}
    if 'FROM retail_product_variants WHERE id=%s FOR UPDATE' in text:
        return {
            'id': 11,
            'stock_on_hand': 3,
            'cost_avg_ars': '120.00',
        }
    return None


class RetailComprasViewTests(unittest.TestCase):
    @patch('service.views.retail_views._tiendanube_schedule_local_variants_sync')
    @patch('service.views.retail_views._load_compra')
    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views.exec_returning')
    @patch('service.views.retail_views.q')
    @patch('service.views.retail_views._set_audit_user')
    def test_post_uses_item_suggested_markup_when_present(
        self,
        _set_audit_user_mock,
        q_mock,
        exec_returning_mock,
        exec_void_mock,
        load_compra_mock,
        _sync_mock,
    ):
        q_mock.side_effect = _q_side_effect
        exec_returning_mock.return_value = 901
        load_compra_mock.return_value = {'id': 901, 'items': []}

        payload = {
            'supplier_name': 'Proveedor X',
            'currency_code': 'ARS',
            'items': [
                {
                    'variant_id': 11,
                    'quantity': 2,
                    'unit_cost_currency': 200,
                    'suggested_markup_pct': 50,
                    'unit_price_final_ars': 320,
                }
            ],
        }
        response = RetailComprasView().post(_request(data=payload))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['id'], 901)

        insert_call = next(
            call
            for call in exec_void_mock.call_args_list
            if 'INSERT INTO retail_purchase_items' in str(call[0][0])
        )
        insert_params = insert_call[0][1]
        self.assertEqual(insert_params[5], Decimal('50.00'))
        self.assertEqual(insert_params[6], Decimal('300.00'))

    @patch('service.views.retail_views._tiendanube_schedule_local_variants_sync')
    @patch('service.views.retail_views._load_compra')
    @patch('service.views.retail_views.exec_void')
    @patch('service.views.retail_views.exec_returning')
    @patch('service.views.retail_views.q')
    @patch('service.views.retail_views._set_audit_user')
    def test_post_fallbacks_to_settings_markup_when_item_markup_missing(
        self,
        _set_audit_user_mock,
        q_mock,
        exec_returning_mock,
        exec_void_mock,
        load_compra_mock,
        _sync_mock,
    ):
        def q_with_custom_default(sql, params=None, one=False):
            text = str(sql)
            if 'SELECT purchase_default_markup_pct FROM retail_settings WHERE id=1' in text:
                return {'purchase_default_markup_pct': '120.00'}
            return _q_side_effect(sql, params=params, one=one)

        q_mock.side_effect = q_with_custom_default
        exec_returning_mock.return_value = 902
        load_compra_mock.return_value = {'id': 902, 'items': []}

        payload = {
            'supplier_name': 'Proveedor X',
            'currency_code': 'ARS',
            'items': [
                {
                    'variant_id': 11,
                    'quantity': 1,
                    'unit_cost_currency': 150,
                    'unit_price_final_ars': 350,
                }
            ],
        }
        response = RetailComprasView().post(_request(data=payload))

        self.assertEqual(response.status_code, 201)
        insert_call = next(
            call
            for call in exec_void_mock.call_args_list
            if 'INSERT INTO retail_purchase_items' in str(call[0][0])
        )
        insert_params = insert_call[0][1]
        self.assertEqual(insert_params[5], Decimal('120.00'))
        self.assertEqual(insert_params[6], Decimal('330.00'))

    @patch('service.views.retail_views._set_audit_user')
    def test_post_rejects_negative_item_markup(
        self,
        _set_audit_user_mock,
    ):
        payload = {
            'supplier_name': 'Proveedor X',
            'currency_code': 'ARS',
            'items': [
                {
                    'variant_id': 11,
                    'quantity': 1,
                    'unit_cost_currency': 150,
                    'suggested_markup_pct': -1,
                    'unit_price_final_ars': 100,
                }
            ],
        }

        with patch('service.views.retail_views.q', side_effect=_q_side_effect), patch(
            'service.views.retail_views.exec_returning',
            return_value=903,
        ):
            with self.assertRaises(ValidationError):
                RetailComprasView().post(_request(data=payload))


if __name__ == '__main__':
    unittest.main()
