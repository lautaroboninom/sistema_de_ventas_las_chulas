from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rest_framework.exceptions import PermissionDenied

from service.views.retail_views import (
    _default_invoice_from_payments,
    _normalize_payment_allocations,
    _resolve_invoice_decision,
)


def _request_with_role(role):
    return SimpleNamespace(user=SimpleNamespace(rol=role))


def _build_account(
    *,
    account_id,
    code,
    method,
    modifier_pct,
    default_arca_account_id=None,
    default_arca_account_code=None,
    default_arca_account_label=None,
):
    return {
        'id': account_id,
        'code': code,
        'label': code.upper(),
        'payment_method': method,
        'active': True,
        'price_modifier_pct': Decimal(str(modifier_pct)).quantize(Decimal('0.01')),
        'default_arca_account_id': default_arca_account_id,
        'default_arca_account_code': default_arca_account_code,
        'default_arca_account_label': default_arca_account_label,
    }


class PaymentInvoiceRulesTests(unittest.TestCase):
    @patch('service.views.retail_views._ensure_payment_account')
    def test_split_base_amounts_apply_per_account_modifiers(self, ensure_payment_account_mock):
        cash_account = _build_account(account_id=1, code='cash', method='cash', modifier_pct='-10')
        credit_account = _build_account(
            account_id=2,
            code='payway',
            method='credit',
            modifier_pct='10',
            default_arca_account_id=22,
            default_arca_account_code='arca-b',
            default_arca_account_label='Cuenta B',
        )
        by_code = {
            cash_account['code']: cash_account,
            credit_account['code']: credit_account,
        }

        def _resolve_account(payload, _method):
            code = payload.get('payment_account_code') or payload.get('account_code')
            return by_code[code]

        ensure_payment_account_mock.side_effect = _resolve_account

        payload = {
            'payments': [
                {'method': 'cash', 'account_code': 'cash', 'amount_ars': 500},
                {'method': 'credit', 'account_code': 'payway', 'amount_ars': 500},
            ]
        }

        result = _normalize_payment_allocations(
            _request_with_role('admin'),
            payload,
            Decimal('1000.00'),
            'cash',
        )

        payments = result['payments']
        self.assertEqual(len(payments), 2)
        self.assertEqual(payments[0]['base_amount_ars'], Decimal('500.00'))
        self.assertEqual(payments[0]['modifier_pct'], Decimal('-10.00'))
        self.assertEqual(payments[0]['amount_ars'], Decimal('450.00'))
        self.assertEqual(payments[1]['base_amount_ars'], Decimal('500.00'))
        self.assertEqual(payments[1]['modifier_pct'], Decimal('10.00'))
        self.assertEqual(payments[1]['amount_ars'], Decimal('550.00'))
        self.assertEqual(result['subtotal_base_ars'], Decimal('1000.00'))
        self.assertEqual(result['effective_modifier_amount_ars'], Decimal('0.00'))
        self.assertEqual(result['effective_modifier_pct'], Decimal('0.00'))
        self.assertEqual(result['total_final_ars'], Decimal('1000.00'))
        self.assertEqual(result['primary_payment_index'], 1)

    @patch('service.views.retail_views._ensure_payment_account')
    def test_modifier_override_requires_admin(self, ensure_payment_account_mock):
        ensure_payment_account_mock.return_value = _build_account(
            account_id=1,
            code='cash',
            method='cash',
            modifier_pct='-10',
        )
        payload = {
            'payments': [
                {'method': 'cash', 'account_code': 'cash', 'amount_ars': 1000, 'modifier_pct': 5},
            ]
        }

        with self.assertRaises(PermissionDenied):
            _normalize_payment_allocations(
                _request_with_role('empleado'),
                payload,
                Decimal('1000.00'),
                'cash',
            )

    def test_default_invoice_uses_payment_account_default_arca(self):
        decision = _default_invoice_from_payments(
            [
                {
                    'amount_ars': Decimal('450.00'),
                    'base_amount_ars': Decimal('500.00'),
                    'default_arca_account_id': None,
                },
                {
                    'amount_ars': Decimal('550.00'),
                    'base_amount_ars': Decimal('500.00'),
                    'default_arca_account_id': 22,
                    'default_arca_account_code': 'arca-b',
                    'default_arca_account_label': 'Cuenta B',
                },
            ]
        )

        self.assertEqual(decision['invoice_mode'], 'arca')
        self.assertTrue(decision['invoice_required'])
        self.assertEqual(decision['arca_account_id'], 22)
        self.assertEqual(decision['arca_account_code'], 'arca-b')
        self.assertEqual(decision['arca_account_label'], 'Cuenta B')
        self.assertEqual(decision['source'], 'default')

    def test_default_invoice_without_arca_defaults_returns_internal(self):
        decision = _default_invoice_from_payments(
            [{'amount_ars': Decimal('1000.00'), 'base_amount_ars': Decimal('1000.00'), 'default_arca_account_id': None}]
        )
        self.assertEqual(decision['invoice_mode'], 'internal')
        self.assertFalse(decision['invoice_required'])
        self.assertIsNone(decision['arca_account_id'])

    def test_invoice_override_is_admin_only(self):
        default_invoice = {
            'invoice_mode': 'arca',
            'invoice_required': True,
            'arca_account_id': 11,
            'arca_account_code': 'arca-a',
            'arca_account_label': 'Cuenta A',
        }
        with self.assertRaises(PermissionDenied):
            _resolve_invoice_decision(_request_with_role('empleado'), default_invoice, {'mode': 'none'})

    def test_admin_can_override_to_none(self):
        default_invoice = {
            'invoice_mode': 'arca',
            'invoice_required': True,
            'arca_account_id': 11,
            'arca_account_code': 'arca-a',
            'arca_account_label': 'Cuenta A',
        }
        decision = _resolve_invoice_decision(_request_with_role('admin'), default_invoice, {'mode': 'none'})
        self.assertEqual(decision['invoice_mode'], 'internal')
        self.assertFalse(decision['invoice_required'])
        self.assertIsNone(decision['arca_account_id'])
        self.assertEqual(decision['source'], 'override')

    @patch('service.views.retail_views._load_arca_account_by_id')
    def test_admin_can_override_to_specific_arca_account(self, load_arca_account_mock):
        load_arca_account_mock.return_value = {
            'id': 22,
            'active': True,
            'code': 'arca-b',
            'label': 'Cuenta B',
        }
        default_invoice = {
            'invoice_mode': 'internal',
            'invoice_required': False,
            'arca_account_id': None,
            'arca_account_code': None,
            'arca_account_label': None,
        }
        decision = _resolve_invoice_decision(
            _request_with_role('admin'),
            default_invoice,
            {'mode': 'arca', 'arca_account_id': 22},
        )
        self.assertEqual(decision['invoice_mode'], 'arca')
        self.assertTrue(decision['invoice_required'])
        self.assertEqual(decision['arca_account_id'], 22)
        self.assertEqual(decision['arca_account_code'], 'arca-b')
        self.assertEqual(decision['arca_account_label'], 'Cuenta B')
        self.assertEqual(decision['source'], 'override')
