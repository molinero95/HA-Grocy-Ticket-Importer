"""Identity-based receipt edits, mapping isolation and uncertain import guards."""
import json
import sqlite3
import unittest
from pathlib import Path
import test_purchase_units as baseline
from receipt_review import mappings, validate_review


class ReviewedPurchaseTests(unittest.TestCase):
    setUp = baseline.PurchaseFlowTests.setUp
    grocy = baseline.PurchaseFlowTests.grocy
    run_import = baseline.PurchaseFlowTests.run_import
    def edit(self, **changes):
        receipt = json.loads(self.receipt.read_text())
        receipt['items'][0].update(original_name='YOG NAT 5', stock_unit='piece', product_mode='new', remember_product=True, **changes)
        self.receipt.write_text(json.dumps(receipt))

    def test_corrected_quantity_preserves_line_cost_and_remembers_only_after_commit(self):
        self.edit(purchase_units='3')
        self.assertIn('15 Piece', self.run_import('--dry-run'))
        self.assertEqual(mappings(self.ledger, 'Test shop'), {})
        self.assertEqual(self.writes, [])
        self.run_import('--commit')
        self.assertEqual(self.amount, 15)
        addition = next(body for route, body in self.writes if route.endswith('/add'))
        self.assertEqual(addition['price'], 0.4)  # original line remains 6 EUR
        saved = mappings(self.ledger, '  TEST SHOP  ')
        self.assertEqual(saved['yog nat 5'], {'product_id': 17, 'stock_unit': 'piece', 'pieces_per_pack': 5})
        self.assertEqual(mappings(self.ledger, 'Other shop'), {})
        writes = len(self.writes)
        self.assertIn('SKIP imported', self.run_import('--commit'))
        self.assertEqual(len(self.writes), writes)

    def test_existing_id_accepts_different_ticket_name_without_catalog_changes(self):
        self.products = [{'id': 17, 'name': 'Yogur natural', 'qu_id_stock': 2, 'qu_id_purchase': 3}]
        self.conversions = [{'product_id': 17, 'from_qu_id': 3, 'to_qu_id': 2, 'factor': 5}]
        self.edit(product_id=17)
        receipt = json.loads(self.receipt.read_text());receipt['items'][0]['product_mode'] = 'existing';self.receipt.write_text(json.dumps(receipt))
        self.run_import('--commit')
        self.assertEqual(self.amount, 10)
        self.assertEqual([route for route, _ in self.writes], ['stock/products/17/add'])

    def test_missing_or_archived_selected_id_never_creates_replacement(self):
        for products in ([], [{'id': 17, 'name': 'Other', 'active': 0, 'qu_id_stock': 2}]):
            self.products = products
            self.edit(product_id=17)
            receipt = json.loads(self.receipt.read_text());receipt['items'][0]['product_mode'] = 'existing';self.receipt.write_text(json.dumps(receipt))
            self.assertIn('REVIEW', self.run_import('--commit'))
            self.assertEqual(self.writes, [])

    def test_new_name_collision_requires_explicit_reuse(self):
        self.products = [{'id': 17, 'name': 'Yogur', 'qu_id_stock': 2, 'qu_id_purchase': 3}]
        self.conversions = [{'product_id': 17, 'from_qu_id': 3, 'to_qu_id': 2, 'factor': 5}]
        self.edit()
        self.assertIn('REVIEW', self.run_import('--commit'))
        self.assertEqual(self.writes, [])

    def test_failed_stock_write_does_not_learn_or_retry(self):
        self.edit()
        original = self.grocy
        def fail(method, route, body=None):
            if route.endswith('/add'): raise OSError('lost response')
            return original(method, route, body)
        self.grocy = fail
        with self.assertRaises(OSError): self.run_import('--commit')
        self.assertEqual(mappings(self.ledger, 'Test shop'), {})
        count = len(self.writes)
        self.assertIn('SKIP pending', self.run_import('--commit'))
        self.assertEqual(len(self.writes), count)

    def test_invalid_review_values_never_reach_grocy(self):
        base = {'name': 'Milk', 'quantity': 1, 'stock_unit': 'piece'}
        for patch in ({'purchase_units': 'NaN'}, {'purchase_units': '-1'}, {'purchase_units': '1.5'}, {'pieces_per_pack': 0}, {'product_mode': 'existing', 'product_id': True}, {'stock_unit': 'kg', 'pieces_per_pack': 2}, {'remember_product': True}):
            with self.subTest(patch=patch), self.assertRaises(ValueError): validate_review({**base, **patch})

    def test_duplicate_explicit_new_names_are_rejected_before_any_write(self):
        self.edit()
        receipt = json.loads(self.receipt.read_text())
        receipt['items'] *= 2
        receipt['total'] = 12
        self.receipt.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'repeated'):
            self.run_import('--commit')
        self.assertEqual(self.writes, [])
