import unittest
from unittest.mock import patch

from service.views.retail_views import (
    _arca_runtime_config,
    _build_credit_note_outcome,
    _build_invoice_outcome,
    _choose_next_arca_account,
)


class ArcaAccountRotationTests(unittest.TestCase):
    def test_choose_next_arca_account_round_robin(self):
        accounts = [
            {'id': 11, 'code': 'a'},
            {'id': 22, 'code': 'b'},
        ]

        self.assertEqual(_choose_next_arca_account(accounts, None)['id'], 11)
        self.assertEqual(_choose_next_arca_account(accounts, 11)['id'], 22)
        self.assertEqual(_choose_next_arca_account(accounts, 22)['id'], 11)

    def test_arca_runtime_config_prefers_account_credentials(self):
        runtime = _arca_runtime_config(
            {'arca_env': 'produccion', 'arca_wsaa_service': 'wsfe'},
            account={
                'arca_cuit': '20-12345678-9',
                'arca_cert_path': 'C:/certs/account-a.crt',
                'arca_key_path': 'C:/certs/account-a.key',
            },
        )

        self.assertEqual(runtime.env, 'produccion')
        self.assertEqual(runtime.cuit, '20123456789')
        self.assertEqual(runtime.cert_path, 'C:/certs/account-a.crt')
        self.assertEqual(runtime.key_path, 'C:/certs/account-a.key')

    @patch('service.views.retail_views._mock_enabled', return_value=True)
    def test_build_invoice_outcome_uses_assigned_account_metadata(self, _mock_enabled):
        outcome = _build_invoice_outcome(
            {'arca_env': 'homologacion', 'arca_wsaa_service': 'wsfe'},
            {
                'id': 5,
                'code': 'legacy-primary',
                'label': 'Cuenta A',
                'arca_cuit': '20123456789',
                'arca_pto_vta_store': 3,
                'arca_pto_vta_online': 7,
                'arca_cbte_tipo_store': 6,
                'arca_cbte_tipo_online': 6,
            },
            {
                'id': 501,
                'channel': 'local',
                'payment_method': 'credit',
                'customer_snapshot': {'doc': '30111222'},
                'total_ars': '1500.00',
            },
            {
                'id': 900,
                'arca_account_id': 5,
                'cbte_nro': 40,
            },
        )

        self.assertEqual(outcome['status'], 'authorized')
        self.assertEqual(outcome['arca_account_id'], 5)
        self.assertEqual(outcome['pto_vta'], 3)
        self.assertEqual(outcome['cbte_tipo'], 6)
        self.assertEqual(outcome['request_payload']['arca_account_code'], 'legacy-primary')
        self.assertEqual(outcome['request_payload']['arca_account_label'], 'Cuenta A')
        self.assertEqual(outcome['request_payload']['issuer_cuit'], '20123456789')

    @patch('service.views.retail_views._mock_enabled', return_value=False)
    def test_build_invoice_outcome_marks_incomplete_account_manual_review(self, _mock_enabled):
        outcome = _build_invoice_outcome(
            {'arca_env': 'produccion', 'arca_wsaa_service': 'wsfe'},
            {
                'id': 5,
                'code': 'arca-secondary',
                'label': 'Cuenta B',
                'arca_cuit': '20999888777',
                'arca_pto_vta_store': 4,
                'arca_pto_vta_online': 8,
                'arca_cbte_tipo_store': 6,
                'arca_cbte_tipo_online': 6,
                'arca_cert_path': '',
                'arca_key_path': '',
            },
            {
                'id': 502,
                'channel': 'online',
                'payment_method': 'credit',
                'customer_snapshot': {'doc': '30111222'},
                'total_ars': '2500.00',
            },
            {
                'id': 901,
                'arca_account_id': 5,
                'cbte_nro': 10,
            },
            missing_doc_policy='manual_review',
        )

        self.assertEqual(outcome['status'], 'manual_review')
        self.assertEqual(outcome['error_code'], 'ARCA_ACCOUNT_INCOMPLETE')

    @patch('service.views.retail_views._mock_enabled', return_value=True)
    def test_credit_note_requires_origin_account(self, _mock_enabled):
        outcome = _build_credit_note_outcome(
            {'arca_env': 'homologacion', 'arca_wsaa_service': 'wsfe'},
            None,
            {
                'id': 700,
                'channel': 'local',
                'customer_snapshot': {'doc': '30111222'},
            },
            {
                'cbte_tipo': 6,
                'cbte_nro': 123,
                'pto_vta': 4,
                'arca_account_id': None,
            },
            {
                'id': 33,
                'amount_total_ars': '500.00',
                'arca_account_id': None,
            },
        )

        self.assertEqual(outcome['status'], 'manual_review')
        self.assertEqual(outcome['error_code'], 'MISSING_ARCA_ACCOUNT')
