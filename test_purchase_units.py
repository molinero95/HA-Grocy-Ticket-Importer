"""Grocy 4 purchase conversions, receipt idempotency and Piece consumption."""
import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import barcode_stock
import importer
from purchase_units import purchase_factor


class PurchaseFlowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.receipt = Path(self.directory.name) / 'receipt.json'
        self.ledger = Path(self.directory.name) / 'ledger.sqlite3'
        self.receipt.write_text(json.dumps({"merchant": "Test shop", "receipt_date": "2026-10-01", "total": 6,
            "source_sha256": "disposable-pack-fixture", "items": [{"name": "Yogur", "quantity": 2, "unit_price": 3, "pieces_per_pack": 5, "purchase_units": "2", "ambiguous": False}]}))
        self.products = []
        self.conversions = []
        self.amount = 0
        self.writes = []
        self.confirm_conversion = True

    def grocy(self, method, path, body=None):
        if method == 'GET':
            return {
                'objects/products': self.products,
                'objects/products/17': {"id": 17, "name": "Yogur", "qu_id_stock": 2},
                'objects/quantity_units': [{"id": 2, "name": "Piece"}, {"id": 3, "name": "Pack"}, {"id": 4, "name": "Kilogram"}],
                'objects/quantity_unit_conversions': self.conversions if self.confirm_conversion else [],
                'stock/products/17': {"stock_amount": self.amount},
            }[path]
        self.writes.append((path, body))
        if path == 'objects/products':
            self.assertNotIn('qu_factor_purchase_to_stock', body)
            self.products.append({**body, 'id': 17})
            return {'created_object_id': 17}
        if path == 'objects/quantity_unit_conversions':
            self.conversions.append(body)
            return {'created_object_id': 1}
        if path == 'stock/products/17/add':
            self.amount += body['amount']
            return {}
        if path == 'stock/products/17/consume':
            self.amount -= body['amount']
            return {}
        raise AssertionError((method, path))

    def run_import(self, mode):
        output = io.StringIO()
        with patch.object(importer, 'DB_PATH', str(self.ledger)), patch.object(importer, 'grocy', side_effect=self.grocy), patch.object(sys, 'argv', ['importer.py', str(self.receipt), mode]), contextlib.redirect_stdout(output):
            importer.main()
        return output.getvalue()

    def test_two_packs_of_five_receipt_then_one_piece_consumed_and_retry_skipped(self):
        self.assertIn('10 Piece', self.run_import('--dry-run'))
        self.assertEqual(self.writes, [])
        self.run_import('--commit')
        self.assertEqual(self.amount, 10)
        self.assertEqual(self.conversions, [{"product_id": 17, "from_qu_id": 3, "to_qu_id": 2, "factor": 5}])
        count = len(self.writes)
        self.assertIn('SKIP imported', self.run_import('--commit'))
        self.assertEqual(len(self.writes), count)
        with patch.object(barcode_stock, 'grocy', side_effect=self.grocy):
            barcode_stock.consume_product_quantity(17, '1', '10')
        self.assertEqual(self.amount, 9)

    def test_existing_pack_product_uses_conversion_without_metadata_changes(self):
        self.products = [{"id": 17, "name": "Yogur", "qu_id_stock": 2, "qu_id_purchase": 3}]
        self.conversions = [{"product_id": 17, "from_qu_id": 3, "to_qu_id": 2, "factor": 5}]
        self.run_import('--commit')
        self.assertEqual(self.amount, 10)
        self.assertEqual([path for path, _ in self.writes], ['stock/products/17/add'])

    def test_mismatched_existing_conversion_requires_review_without_writes(self):
        self.products = [{"id": 17, "name": "Yogur", "qu_id_stock": 2, "qu_id_purchase": 3}]
        self.conversions = [{"product_id": 17, "from_qu_id": 3, "to_qu_id": 2, "factor": 6}]
        self.assertIn('REVIEW', self.run_import('--commit'))
        self.assertEqual(self.writes, [])

    def test_failed_conversion_verification_never_writes_stock_or_recreates_product(self):
        self.confirm_conversion = False
        with self.assertRaises(ValueError):
            self.run_import('--commit')
        self.assertEqual(self.amount, 0)
        with sqlite3.connect(self.ledger) as db:
            self.assertEqual(db.execute('SELECT state FROM receipt_items').fetchone()[0], 'pending')
        count = len(self.writes)
        self.assertIn('SKIP pending', self.run_import('--commit'))
        self.assertEqual(len(self.writes), count)

    def test_ambiguous_or_invalid_factor_fails_closed(self):
        self.conversions = [{"product_id": 17, "from_qu_id": 3, "to_qu_id": 2, "factor": 'NaN'}]
        with self.assertRaises(ValueError):
            purchase_factor(self.grocy, 17, 3, 2)
        self.conversions *= 2
        with self.assertRaises(ValueError):
            purchase_factor(self.grocy, 17, 3, 2)
