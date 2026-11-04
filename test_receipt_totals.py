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

    def test_monetary_mismatch_is_advisory_without_changing_quantities_or_prices(self):
        data = receipt()
        data['total'] = 77.00
        before = json.dumps(data)
        importer.validate(data)
        self.assertIn('no bloquea', importer.total_warning(data))
        self.assertEqual(json.dumps(data), before)

    def test_gross_lines_and_unallocated_discount_do_not_mark_stock_ambiguous(self):
        data = {'merchant': 'Synthetic shop', 'receipt_date': '2026-01-01', 'total': 7.04,
                'items': [{'name': 'Product ' + str(i), 'quantity': 1, 'unit_price': price, 'ambiguous': False, 'reason': ''}
                          for i, price in enumerate((.95, 3.90, 2.55, .15))]}
        response = MockResponse()
        response.read = lambda: json.dumps({'output': [{'content': [{'type': 'output_text', 'text': json.dumps(data)}]}]}).encode()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'synthetic.pdf';path.write_bytes(b'disposable receipt')
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'disposable'}), patch('urllib.request.urlopen', return_value=response):
                result = extract.extract(path)
        importer.validate(result)
        self.assertIn('7.55', result['total_warning']);self.assertIn('7.04', result['total_warning'])
        self.assertFalse(any(item['ambiguous'] for item in result['items']))
        self.assertEqual([i['quantity'] for i in result['items']], [1, 1, 1, 1])

    def test_legacy_total_only_flags_are_ignored_but_real_uncertainty_remains(self):
        base = {'name': 'Product', 'quantity': 1, 'ambiguous': True}
        self.assertEqual(importer.classify({**base, 'reason': 'Receipt total mismatch'})[0], 'STOCK')
        for reason in ('Uncertain quantity', 'Unclear product Receipt total mismatch'):
            self.assertEqual(importer.classify({**base, 'reason': reason})[0], 'REVIEW')

    def test_carry_bags_are_nonstock_but_food_bags_are_not(self):
        from receipt_review import is_shopping_bag
        for name in ('Bolsa', 'BOLSA 50% RECICLADA', 'Bolsa de papel', 'Bolsa reutilizable'):
            self.assertTrue(is_shopping_bag(name), name)
            self.assertEqual(importer.classify({'name': name, 'quantity': 1})[0], 'EXPENSE')
        for name in ('Hielo bolsa 2 kg', 'Bolsa de patatas', 'Bolsa basura 50 l', 'Bolsa de pan', 'Patata bolsa 2 kg'):
            self.assertFalse(is_shopping_bag(name), name)

    def test_invalid_stock_numbers_and_negative_prices_still_fail(self):
        for field, value in (('quantity', 0), ('quantity', 'NaN'), ('unit_price', -1)):
            data = receipt();data['items'][0][field] = value
            with self.assertRaises(ValueError): importer.validate(data)

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
