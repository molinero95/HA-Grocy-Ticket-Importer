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

    def test_explicit_existing_addition_preserves_original_cost_and_purchase_conversion(self):
        self.products = [{'id': 17, 'name': 'Yogur natural', 'qu_id_stock': 2, 'qu_id_purchase': 3}]
        self.conversions = [{'product_id': 17, 'from_qu_id': 3, 'to_qu_id': 2, 'factor': 5}]
        self.amount = 5
        self.edit(product_id=17, stock_to_add='3', expected_stock='5')
        receipt = json.loads(self.receipt.read_text());receipt['items'][0]['product_mode'] = 'existing';self.receipt.write_text(json.dumps(receipt))
        self.assertIn('3 Piece', self.run_import('--dry-run'))
        self.assertEqual(self.writes, [])
        self.run_import('--commit');self.assertEqual(self.amount, 8)
        self.assertEqual(self.writes, [('stock/products/17/add', {'amount': 3.0, 'price': 2.0, 'best_before_date': '2999-12-31', 'location_id': int(__import__('os').environ.get('GROCY_LOCATION_ID','2')), 'note': self.writes[0][1]['note']})])
        self.assertEqual(self.conversions[0]['factor'], 5)
        self.assertIn('SKIP imported', self.run_import('--commit'));self.assertEqual(self.amount, 8)

    def test_explicit_addition_rejects_stale_stock_before_any_write(self):
        self.products = [{'id': 17, 'name': 'Yogur natural', 'qu_id_stock': 2, 'qu_id_purchase': 3}]
        self.conversions = [{'product_id': 17, 'from_qu_id': 3, 'to_qu_id': 2, 'factor': 5}]
        self.edit(product_id=17, stock_to_add='3', expected_stock='5')
        receipt = json.loads(self.receipt.read_text());receipt['items'][0]['product_mode'] = 'existing';self.receipt.write_text(json.dumps(receipt))
        self.assertIn('REVIEW', self.run_import('--commit'))
        self.assertEqual(self.writes, [])

    def test_direct_addition_validation_and_advisory_ranking(self):
        from receipt_review import suggestions
        base = {'name': 'Yogur', 'quantity': 1, 'stock_unit': 'piece', 'product_mode': 'existing', 'product_id': 17, 'stock_to_add': '3', 'expected_stock': '5'}
        for value in ('0', 'NaN', '1.5', '-1', '1000001'):
            with self.subTest(value=value), self.assertRaises(ValueError): validate_review({**base, 'stock_to_add': value})
        self.assertEqual(suggestions('YOGUR NAT', [{'id': 1, 'name': 'Lejia'}, {'id': 2, 'name': 'Yogur natural'}]), [2])
        self.assertEqual(suggestions('XYZ999', [{'id': 2, 'name': 'Yogur natural'}]), [])

    def test_multiple_explicit_lines_check_same_starting_stock_before_writing(self):
        self.products = [{'id': 17, 'name': 'Yogur natural', 'qu_id_stock': 2, 'qu_id_purchase': 3}]
        self.conversions = [{'product_id': 17, 'from_qu_id': 3, 'to_qu_id': 2, 'factor': 5}]
        self.amount = 5
        self.edit(product_id=17, stock_to_add='3', expected_stock='5')
        receipt = json.loads(self.receipt.read_text());receipt['items'][0]['product_mode'] = 'existing'
        receipt['items'].append({**receipt['items'][0], 'stock_to_add': '4'});receipt['total'] = 12
        self.receipt.write_text(json.dumps(receipt))
        self.run_import('--commit');self.assertEqual(self.amount, 12)
        self.assertEqual(len(self.writes), 2)
        self.assertIn('SKIP imported', self.run_import('--commit'));self.assertEqual(self.amount, 12)

    def test_omitted_line_keeps_total_and_never_creates_stock_or_remembered_mapping(self):
        self.edit(purchase_units='0')
        receipt = json.loads(self.receipt.read_text());receipt['items'][0].update(product_mode='skip', remember_product=False, pieces_per_pack=0)
        self.receipt.write_text(json.dumps(receipt))
        self.assertIn('WOULD OMIT', self.run_import('--dry-run'));self.assertEqual(self.writes, [])
        self.run_import('--commit');self.assertEqual(self.writes, [])
        with sqlite3.connect(self.ledger) as db: self.assertEqual(db.execute('SELECT product_id,state FROM receipt_items').fetchall(), [(None, 'omitted')])
        self.assertEqual(mappings(self.ledger, 'Test shop'), {})
        receipt['items'][0].update(product_mode='new', remember_product=True, purchase_units='2', pieces_per_pack=5)
        self.receipt.write_text(json.dumps(receipt))
        self.assertIn('SKIP omitted', self.run_import('--commit'));self.assertEqual(self.writes, [])

    def test_omission_cannot_bypass_an_uncertain_pending_line(self):
        from receipt_review import has_review
        with sqlite3.connect(self.ledger) as db:
            db.execute('CREATE TABLE receipt_items (receipt_hash TEXT, line INTEGER, product_id INTEGER, state TEXT, detail TEXT, PRIMARY KEY(receipt_hash,line))')
            db.execute("INSERT INTO receipt_items VALUES ('disposable-pack-fixture',0,17,'pending','uncertain')")
        receipt = json.loads(self.receipt.read_text());receipt['items'][0].update(product_mode='skip', remember_product=False)
        self.receipt.write_text(json.dumps(receipt))
        output = self.run_import('--commit');self.assertTrue(has_review(output));self.assertIn('SKIP pending', output);self.assertEqual(self.writes, [])

    def test_omitted_original_cost_is_still_in_total_validation(self):
        receipt = json.loads(self.receipt.read_text());receipt['items'][0].update(product_mode='skip', remember_product=False);receipt['total'] = 1
        self.receipt.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'Total mismatch'): self.run_import('--commit')
        self.assertEqual(self.writes, [])

    def test_review_issues_translate_actual_row_numbers_and_pending_guards(self):
        from receipt_review import review_issues
        issues = review_issues('[1] REVIEW Product: Stock changed since receipt review\n[2] WOULD OMIT charge\n[3] SKIP pending Product')
        self.assertEqual([item['index'] for item in issues], [0, 2])
        self.assertIn('Actualizar stock y catálogo', issues[0]['message'])
        self.assertIn('importación anterior pendiente', issues[1]['message'])
