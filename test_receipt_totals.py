"""Regression tests for per-line rounding. No network calls."""
import unittest
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import patch
import json
import os
import tempfile
from pathlib import Path

import extract
import importer

LINES = [
    ('1', '3.75'), ('.29', '9.95'), ('.52', '5.75'), ('.135', '8.79'),
    ('1.305', '6.99'), ('3', '1.75'), ('1', '2.99'), ('3', '.15'),
    ('1', '2.59'), ('1', '.95'), ('1', '2.99'), ('1', '2.89'),
    ('1', '2.25'), ('1', '3.15'), ('.27', '2.79'), ('1.03', '1.19'),
    ('4', '1.34'), ('1.095', '17.95'), ('1', '2'), ('2', '1.05'), ('2', '1.765'),
]

def receipt():
    return {'merchant': 'Example market', 'receipt_date': '2026-09-28',
            'total': 78.08,
            'items': [{'name': f'Item {i}', 'quantity': float(q),
                       'unit_price': float(p), 'ambiguous': False, 'reason': ''}
                      for i, (q, p) in enumerate(LINES, 1)]}

class MockResponse:
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self):
        return json.dumps({'output': [{'content': [{'type': 'output_text',
                            'text': json.dumps(receipt())}]}]}).encode()

class ReceiptTotalsTests(unittest.TestCase):
    def test_line_rounding_matches_receipt(self):
        importer.validate(receipt())
        total = sum((Decimal(q) * Decimal(p)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    for q, p in LINES)
        self.assertEqual(total, Decimal('78.08'))

    def test_real_mismatch_is_rejected(self):
        data = receipt()
        data['total'] = 77.00
        with self.assertRaisesRegex(ValueError, 'Total mismatch'):
            importer.validate(data)

    def test_fractional_unit_price_is_not_rounded_early(self):
        self.assertEqual(importer.money(Decimal('2') * Decimal('1.765')), Decimal('3.53'))

    def test_packaged_potatoes_use_piece(self):
        item = {'name': 'Patata Meleiro bolsa 2,5 kg', 'quantity': 1, 'ambiguous': False}
        self.assertEqual(importer.classify(item)[0:2], ('STOCK', 2))

    def test_fish_with_size_range_uses_kilogram(self):
        item = {'name': 'Lubina kg (800-1200 g)', 'quantity': 1.095, 'ambiguous': False}
        self.assertEqual(importer.classify(item)[0:2], ('STOCK', 4))

    def test_discount_stays_in_review(self):
        item = {'name': 'Pasta Gallo ensaladas hélices 400 g', 'quantity': 2,
                'ambiguous': True, 'reason': 'Discount applied on second unit'}
        self.assertEqual(importer.classify(item)[0], 'REVIEW')

    def test_extraction_does_not_flag_rounding_as_ambiguity(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'dummy.pdf'
            path.write_bytes(b'%PDF-1.4 test')
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'test'}):
                with patch('urllib.request.urlopen', return_value=MockResponse()):
                    data = extract.extract(path)
        self.assertEqual(sum(item['ambiguous'] for item in data['items']), 0)

if __name__ == '__main__':
    unittest.main()
