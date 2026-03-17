import unittest

from rest_framework.exceptions import ValidationError

from service.views.retail_views import (
    LABEL_LAYOUT_A4_GRID,
    LABEL_LAYOUT_THERMAL_CUSTOM,
    _build_barcodes_labels_pdf,
    _ean13_check_digit,
    _ean13_is_valid,
)


class Ean13BarcodeTests(unittest.TestCase):
    def _variant_payload(self):
        return {
            'id': 1,
            'producto': 'Remera Basica',
            'sku': 'RM-001',
            'option_values': [
                {'attribute_name': 'Color', 'option_value': 'Negro'},
                {'attribute_name': 'Talle', 'option_value': 'M'},
            ],
            'price_store_ars': '15990.50',
        }

    def test_checksum_generation_and_validation(self):
        base12 = '779000000001'
        code = f'{base12}{_ean13_check_digit(base12)}'
        self.assertEqual(len(code), 13)
        self.assertTrue(_ean13_is_valid(code))

    def test_invalid_checksum_is_rejected(self):
        self.assertFalse(_ean13_is_valid('7790000000011'))
        self.assertFalse(_ean13_is_valid('123456789012'))
        self.assertFalse(_ean13_is_valid('ABC'))

    def test_labels_pdf_is_generated_a4_grid(self):
        base12 = '779000000123'
        code = f'{base12}{_ean13_check_digit(base12)}'
        payload = _build_barcodes_labels_pdf(
            self._variant_payload(),
            [{'barcode': code, 'is_primary': True}],
            copies=1,
            layout=LABEL_LAYOUT_A4_GRID,
        )
        self.assertTrue(payload.startswith(b'%PDF-'))
        self.assertGreater(len(payload), 1000)

    def test_labels_pdf_is_generated_thermal_custom(self):
        base12 = '779000000124'
        code = f'{base12}{_ean13_check_digit(base12)}'
        payload = _build_barcodes_labels_pdf(
            self._variant_payload(),
            [{'barcode': code, 'is_primary': True}],
            copies=1,
            layout=LABEL_LAYOUT_THERMAL_CUSTOM,
            label_width_mm=50,
            label_height_mm=30,
        )
        self.assertTrue(payload.startswith(b'%PDF-'))
        self.assertGreater(len(payload), 800)

    def test_labels_pdf_validation_errors(self):
        base12 = '779000000125'
        code = f'{base12}{_ean13_check_digit(base12)}'
        variant = self._variant_payload()
        rows = [{'barcode': code, 'is_primary': True}]

        with self.assertRaises(ValidationError):
            _build_barcodes_labels_pdf(variant, rows, copies=1, layout='legacy')

        with self.assertRaises(ValidationError):
            _build_barcodes_labels_pdf(
                variant,
                rows,
                copies=1,
                layout=LABEL_LAYOUT_THERMAL_CUSTOM,
                label_width_mm=0,
                label_height_mm=30,
            )

        with self.assertRaises(ValidationError):
            _build_barcodes_labels_pdf(
                variant,
                rows,
                copies=1,
                layout=LABEL_LAYOUT_THERMAL_CUSTOM,
                label_width_mm=50,
                label_height_mm='',
            )


if __name__ == '__main__':
    unittest.main()
