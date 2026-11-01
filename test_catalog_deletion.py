"""Guard irreversible Grocy deletion, local references and uncertain outcomes."""
import copy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from unittest.mock import patch

import barcode_stock
import catalog_lifecycle as lifecycle
import shopping_match_queue as queue
import shopping_sync_worker as worker
import variant_catalog
from generic_catalog import connect, register_generic, register_variant
from shopping_aliases import set_alias
from shopping_identity_runtime import save_identity_state
with patch.dict(os.environ, WEB_PASSWORD='test-password', WEB_SESSION_SECRET='test-secret-key'):
    import web


class DeletionFixture:
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.product = {'id': 7, 'name': 'Sin uso', 'active': 0, 'parent_product_id': None}
        self.amount = '0'
        self.version = '4.7.1'
        self.rows = {key: [] for key in ('stock', 'stock_log', 'shopping_list', 'recipes_pos',
                                        'recipes', 'meal_plan', 'products', 'product_barcodes', 'quantity_unit_conversions')}
        self.deleted = False
        self.uncertain = False
        for mock in (patch.object(variant_catalog, 'CATALOG_DB', self.root / 'variants.sqlite3'),
                     patch.object(queue, 'BASE_PATH', self.root / 'queue.sqlite3'),
                     patch.object(queue, 'DEFAULT_PATH', self.root / 'queue-current.sqlite3'),
                     patch.object(worker, 'STATE_V2', self.root / 'shopping-sync-current-identity-v2.json'),
                     patch.dict(os.environ, GROCY_IMPORT_DB=str(self.root / 'imports.sqlite3'),
                                STOCK_COMMAND_DB=str(self.root / 'commands.sqlite3')),
                     patch.object(barcode_stock, 'grocy', side_effect=self.grocy)):
            value = mock.start(); self.addCleanup(mock.stop)
            if getattr(mock, 'attribute', None) == 'grocy': self.mock_grocy = value

    def grocy(self, method, path, body=None):
        if method == 'DELETE':
            self.assertEqual(path, 'objects/products/7')
            self.deleted = True
            self.rows['stock_log'] = [row for row in self.rows['stock_log'] if row['product_id'] != 7]
            if self.uncertain: raise ConnectionError('private endpoint')
            return {}
        self.assertEqual(method, 'GET')
        if path == 'system/info': return {'grocy_version': {'Version': self.version}}
        if path == 'objects/products/7': return dict(self.product)
        if path == 'objects/stock' and self.amount != '0':
            return [{'id': 30, 'product_id': 7, 'amount': self.amount}]
        if path == 'objects/products': return [] if self.deleted else [dict(self.product), *copy.deepcopy(self.rows['products'])]
        return copy.deepcopy(self.rows[path.removeprefix('objects/')])

    def assert_no_write(self):
        self.assertTrue(all(call.args[0] == 'GET' for call in self.mock_grocy.call_args_list))



class DeletionTests(DeletionFixture, unittest.TestCase):
    def test_clean_archived_product_allows_one_verified_delete_of_owned_metadata(self):
        self.rows['product_barcodes'] = [{'id': 1, 'product_id': 7, 'barcode': '8412345678901'}]
        self.rows['quantity_unit_conversions'] = [{'id': 1, 'product_id': 7, 'factor': 5}]
        preview = lifecycle.deletion_preview(7)
        self.assertTrue(preview['allowed'])
        self.assertEqual((preview['barcode_count'], preview['conversion_count']), (1, 1))
        self.assert_no_write()
        self.assertEqual(lifecycle.delete_archived(7, 'Sin uso', preview['token']), {'deleted': True, 'product_id': 7})
        self.assertEqual([call.args for call in self.mock_grocy.call_args_list if call.args[0] != 'GET'], [('DELETE', 'objects/products/7')])

    def test_every_grocy_history_and_dependency_blocks_deletion(self):
        for collection in ('stock', 'shopping_list', 'recipes_pos', 'recipes', 'meal_plan', 'products'):
            with self.subTest(collection=collection):
                field = 'parent_product_id' if collection == 'products' else 'product_id'
                self.rows[collection] = [{'id': 50, field: 7, **({'amount': 0} if collection == 'stock' else {})}]
                preview = lifecycle.deletion_preview(7)
                self.assertFalse(preview['allowed'])
                with self.assertRaises(barcode_stock.BarcodeError):
                    lifecycle.delete_archived(7, 'Sin uso', preview['token'])
                self.rows[collection] = []
        self.assert_no_write()

    def test_active_nonzero_nan_and_unknown_stock_fail_closed(self):
        self.product['active'] = 1
        self.assertFalse(lifecycle.deletion_preview(7)['allowed'])
        self.product['active'] = 0
        for amount in ('1', '-1', 'NaN', 'Infinity'):
            self.amount = amount
            self.assertFalse(lifecycle.deletion_preview(7)['allowed'])
        self.amount = None
        with self.assertRaises(ArithmeticError): lifecycle.deletion_preview(7)
        self.assert_no_write()

    def test_stale_confirmation_rechecks_product_and_owned_barcodes(self):
        token = lifecycle.deletion_preview(7)['token']
        self.rows['product_barcodes'] = [{'id': 1, 'product_id': 7, 'barcode': '8412345678901'}]
        with self.assertRaisesRegex(barcode_stock.BarcodeError, 'han cambiado'):
            lifecycle.delete_archived(7, 'Sin uso', token)
        token = lifecycle.deletion_preview(7)['token']
        self.product['active'] = 1
        with self.assertRaises(barcode_stock.BarcodeError): lifecycle.delete_archived(7, 'Sin uso', token)
        self.assert_no_write()

    def test_unverified_grocy_version_blocks_unreviewed_cascades(self):
        self.version = '4.8.0'
        preview = lifecycle.deletion_preview(7)
        self.assertFalse(preview['allowed'])
        with self.assertRaises(barcode_stock.BarcodeError):
            lifecycle.delete_archived(7, 'Sin uso', preview['token'])
        self.assert_no_write()

    def test_incomplete_reference_read_cannot_authorize_deletion(self):
        self.rows['stock_log'] = {'unexpected': 'response'}
        with self.assertRaises(ValueError): lifecycle.deletion_preview(7)
        self.assert_no_write()

    def test_local_variants_aliases_receipts_and_scoped_checkpoints_are_preserved(self):
        with connect(variant_catalog.CATALOG_DB) as db:
            gid = register_generic(db, 7, 'Sin uso')
            register_variant(db, gid, '8412345678901', 'Variante', grocy_barcode_owners={7})
        set_alias(self.root / 'queue-other.sqlite3', 'Alias', 7)
        with sqlite3.connect(self.root / 'imports.sqlite3') as db:
            db.execute('CREATE TABLE receipt_items(product_id INTEGER, state TEXT)')
            db.execute("INSERT INTO receipt_items VALUES(7,'pending')")
        save_identity_state(self.root / 'shopping-sync-other-identity-v2.json', ['p:7'], {'alias': 7})
        before = {path: path.read_bytes() for path in self.root.iterdir() if path.is_file()}
        preview = lifecycle.deletion_preview(7)
        self.assertFalse(preview['allowed'])
        for reason in ('variantes asociadas', 'alias de Alexa', 'una importación de ticket pendiente de comprobar', 'sincronización de Alexa aún vinculada'):
            self.assertIn(reason, preview['blockers'])
        for path, original in before.items(): self.assertEqual(path.read_bytes(), original)
        self.assert_no_write()

    def test_movement_history_requires_explicit_acknowledgement_and_is_then_deleted(self):
        self.rows['stock_log'] = [{'id': 1, 'product_id': 7, 'amount': 2}]
        preview = lifecycle.deletion_preview(7)
        self.assertTrue(preview['allowed'])
        self.assertEqual(preview['history_count'], 1)
        with self.assertRaisesRegex(barcode_stock.BarcodeError, 'Confirma expresamente'):
            lifecycle.delete_archived(7, 'Sin uso', preview['token'])
        self.assert_no_write()
        lifecycle.delete_archived(7, 'Sin uso', preview['token'], delete_history=True)
        self.assertEqual(self.rows['stock_log'], [])

    def test_completed_receipt_ledger_is_retained_without_blocking_confirmed_deletion(self):
        path = self.root / 'imports.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE receipt_items(product_id INTEGER, state TEXT)')
            db.execute("INSERT INTO receipt_items VALUES(7,'imported')")
        before = path.read_bytes()
        preview = lifecycle.deletion_preview(7)
        self.assertTrue(preview['allowed'])
        lifecycle.delete_archived(7, 'Sin uso', preview['token'])
        self.assertEqual(path.read_bytes(), before)

    def test_pending_alexa_choices_and_removals_block_without_deleting_queue(self):
        with queue.connect(queue.DEFAULT_PATH) as db:
            db.execute("INSERT INTO pending_matches(normalized_name,original_name,candidates_json,selected_product_id,removal_json) VALUES('alias','Alias','[]',7,?)", (json.dumps({'product_id': 7}),))
        preview = lifecycle.deletion_preview(7)
        self.assertIn('una elección pendiente de Alexa', preview['blockers'])
        self.assertIn('una retirada pendiente de Alexa', preview['blockers'])
        self.assert_no_write()

    def test_corrupt_existing_local_state_blocks_instead_of_ignoring_references(self):
        worker.STATE_V2.write_text('{broken')
        with self.assertRaises(ValueError): lifecycle.deletion_preview(7)
        self.assert_no_write()


class DeletionApiTests(DeletionFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        for mock in (patch.object(web, 'INGRESS_MODE', True), patch.dict(web.app.config, SECRET_KEY='delete-test-session'),
                     patch.dict(os.environ, WEB_PASSWORD='test-password')):
            mock.start(); self.addCleanup(mock.stop)
        self.client = web.app.test_client()
        self.headers = {'X-CSRF-Token': self.client.get('/api/v1/auth/status').json['csrf_token']}

    def payload(self):
        preview = self.client.get('/api/v1/catalog/products/7/deletion')
        self.assertEqual(preview.status_code, 200, preview.json)
        return {'expected_name': 'Sin uso', 'confirmation': 'Sin uso', 'token': preview.json['token'], 'operation_id': str(uuid.uuid4())}

    def test_auth_csrf_and_exact_typed_confirmation_precede_dispatch(self):
        with patch.object(web, 'INGRESS_MODE', False):
            self.assertEqual(self.client.get('/api/v1/catalog/products/7/deletion').status_code, 401)
        self.assertEqual(self.client.delete('/api/v1/catalog/products/7', json={}).status_code, 403)
        payload = self.payload(); payload['confirmation'] = 'incorrect'
        self.assertEqual(self.client.delete('/api/v1/catalog/products/7', json=payload, headers=self.headers).status_code, 400)
        self.assert_no_write()

    def test_repeated_operation_replays_response_without_another_delete(self):
        payload = self.payload()
        for _ in range(2):
            response = self.client.delete('/api/v1/catalog/products/7', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(sum(call.args[0] == 'DELETE' for call in self.mock_grocy.call_args_list), 1)

    def test_uncertain_delete_is_never_replayed_and_errors_are_sanitized(self):
        payload = self.payload(); self.uncertain = True
        for status in (502, 409):
            response = self.client.delete('/api/v1/catalog/products/7', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, status, response.json)
            self.assertNotIn('private endpoint', response.get_data(as_text=True))
        self.assertEqual(sum(call.args[0] == 'DELETE' for call in self.mock_grocy.call_args_list), 1)

    def test_reference_added_after_review_rejects_delete(self):
        payload = self.payload()
        self.rows['stock_log'] = [{'id': 2, 'product_id': 7}]
        self.assertEqual(self.client.delete('/api/v1/catalog/products/7', json=payload, headers=self.headers).status_code, 409)
        self.assert_no_write()
