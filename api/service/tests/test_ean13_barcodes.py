import unittest

from service.views.retail_views import (
    _build_barcodes_labels_pdf,
    _ean13_check_digit,
    _ean13_is_valid,
)


class Ean13BarcodeTests(unittest.TestCase):
    def test_checksum_generation_and_validation(self):
        base12 = '779000000001'
        code = f'{base12}{_ean13_check_digit(base12)}'
        self.assertEqual(len(code), 13)
        self.assertTrue(_ean13_is_valid(code))

    def test_invalid_checksum_is_rejected(self):
        self.assertFalse(_ean13_is_valid('7790000000011'))
        self.assertFalse(_ean13_is_valid('123456789012'))
        self.assertFalse(_ean13_is_valid('ABC'))

    def test_labels_pdf_is_generated(self):
        base12 = '779000000123'
        code = f'{base12}{_ean13_check_digit(base12)}'
        payload = _build_barcodes_labels_pdf(
            {'id': 1, 'producto': 'Remera', 'sku': 'RM-001', 'option_signature': 'Color=Negro,Talle=M'},
            [{'barcode': code, 'is_primary': True}],
            copies=1,
        )
        self.assertTrue(payload.startswith(b'%PDF-'))
        self.assertGreater(len(payload), 1000)


if __name__ == '__main__':
    unittest.main()
