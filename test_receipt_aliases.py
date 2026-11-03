import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from receipt_review import remember, list_aliases, change_alias, mappings
with patch.dict(os.environ, WEB_PASSWORD='test-password', WEB_SESSION_SECRET='test-secret-key'):
    import web
import importer

class ReceiptAliasTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.db = Path(temp.name)/'ledger.sqlite3'
        self.products = [{'id': 1, 'name': 'Uno', 'stock_unit': 'piece', 'pieces_per_pack': 1}, {'id': 2, 'name': 'Dos', 'stock_unit': 'kg', 'pieces_per_pack': 1}]
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE receipt_items (receipt_hash TEXT, state TEXT)')
            db.execute("INSERT INTO receipt_items VALUES ('already-imported','imported')")
            for shop in ('Mercado A', 'Mercado B'):
                remember(db, shop, {'name': 'LECHE ENTERA', 'remember_product': True, 'stock_unit': 'piece'}, 1)
        self.original = list_aliases(self.db)[0]

    def payload(self, **values): return {'expected': self.original, 'merchant': 'Mercado A', 'source_name': 'LECHE', 'product_id': 2, **values}

    def test_edit_preserves_other_merchants_and_ledger_and_rejects_stale_delete(self):
        change_alias(self.db, self.payload(), self.products)
        self.assertEqual(mappings(self.db, 'Mercado A')['leche']['stock_unit'], 'kg')
        self.assertEqual(mappings(self.db, 'Mercado B')['leche entera']['product_id'], 1)
        with self.assertRaises(ValueError): change_alias(self.db, {'expected': self.original}, [], delete=True)
        with sqlite3.connect(self.db) as db: self.assertEqual(db.execute('SELECT * FROM receipt_items').fetchall(), [('already-imported', 'imported')])

    def test_collision_invalid_product_and_failed_validation_preserve_all_rows(self):
        before = list_aliases(self.db)
        for change in ({'merchant': 'Mercado B', 'source_name': 'leche entera'}, {'product_id': True}, {'product_id': 999}, {'source_name': ''}, {'merchant': 'x'*201}):
            with self.subTest(change=change), self.assertRaises(ValueError): change_alias(self.db, self.payload(**change), self.products)
            self.assertEqual(list_aliases(self.db), before)

    def test_delete_only_one_mapping_and_empty_read_does_not_create_database(self):
        missing = self.db.parent/'missing.sqlite3'
        self.assertEqual(list_aliases(missing), []);self.assertFalse(missing.exists())
        change_alias(self.db, {'expected': self.original}, [], delete=True)
        self.assertEqual(len(list_aliases(self.db)), 1)

    def test_api_requires_auth_csrf_and_does_not_write_grocy(self):
        with patch.dict(os.environ, WEB_PASSWORD='test-password'), patch.object(web, 'INGRESS_MODE', True), patch.object(importer, 'DB_PATH', self.db), patch('api_receipts.receipt_catalog', return_value=self.products), patch.object(importer, 'grocy', side_effect=AssertionError('No remote mutations')):
            client = web.app.test_client();headers = {'X-CSRF-Token': client.get('/api/v1/auth/status').json['csrf_token']}
            self.assertEqual(len(client.get('/api/v1/receipt-aliases').json['aliases']), 2)
            self.assertEqual(client.put('/api/v1/receipt-aliases', json=self.payload()).status_code, 403)
            self.assertEqual(client.put('/api/v1/receipt-aliases', json=self.payload(), headers=headers).status_code, 200)
            with patch.object(web, 'INGRESS_MODE', False): self.assertEqual(client.get('/api/v1/receipt-aliases').status_code, 401)
